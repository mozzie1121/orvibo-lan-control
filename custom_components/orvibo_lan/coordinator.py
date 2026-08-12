"""Home Assistant coordinator for cloud metadata and LAN gateway state."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from contextlib import suppress

import aiohttp
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, GATEWAY_DISCOVER_INTERVAL, UPDATE_INTERVAL
from .device_profiles import (
    PROPERTY_BATTERY_POWER,
    PROPERTY_DOOR_STATUS,
    normalize_device_type,
    normalize_readtable_devices,
    property_percentage,
    property_switch_state,
    state_properties,
)
from .exceptions import OrviboLanError, StateStoreError
from .gateway_manager import GatewayManager
from .lib.cloud_client import CloudAuthenticationError, CloudClient
from .lib.gateway_connection import GatewayConnectionError
from .lib.packet import CMD_STATE_UPDATE
from .models import StateSource, StateUpdate
from .privacy import mask_host, mask_identifier
from .state_store import StateStore

_LOGGER = logging.getLogger(__name__)

_MAX_DEVICES = 1000
_CONTROL_TIMEOUT = 8.0
_STATE_NUMBER_FIELDS = frozenset(("value1", "value2", "value3", "value4"))
_STATE_NUMBER_MIN = -(1 << 31)
_STATE_NUMBER_MAX = (1 << 32) - 1
_DERIVED_STATE_FIELDS = frozenset(
    (
        "battery",
        "door_state",
        "emergency_state",
        "gas_detected",
        "humidity",
        "motion_detected",
        "property_door_open",
        "smoke_detected",
        "temperature",
        "water_leak_detected",
    )
)
_LAN_METADATA_FIELDS = frozenset(
    (
        "cmd",
        "debugInfo",
        "gatewayUID",
        "gatewayUid",
        "serial",
        "serverRecord",
        "source",
        "uid",
        "uniSerial",
        "userName",
        "ver",
    )
)


class OrviboLanCoordinator(DataUpdateCoordinator[dict[str, dict[str, object]]]):
    """Own the cloud client, gateway manager, and merged device state."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        family_id: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=UPDATE_INTERVAL,
        )
        self.username = username
        self.password = password
        self.family_id = family_id
        self.cloud_client = CloudClient(session, username, password, family_id)
        self.gateway_manager: GatewayManager | None = None
        self.devices: dict[str, dict[str, object]] = {}
        self.device_states: dict[str, dict[str, object]] = {}
        self.device_types: dict[str, int] = {}
        self.room_names: dict[str, str] = {}
        self._gateway_ips: dict[str, str] = {}
        self._state_store: StateStore | None = None
        self._cloud_generation = 0
        self._lan_generation = 0
        self._discover_task: asyncio.Task[None] | None = None
        self._notify_task: asyncio.Task[None] | None = None
        self._closed = False

    async def async_setup(self) -> None:
        """Authenticate, load initial state, and start managed gateway services."""

        try:
            await self.cloud_client.login()
        except CloudAuthenticationError as err:
            raise ConfigEntryAuthFailed("ORVIBO cloud authentication failed") from err
        except OrviboLanError as err:
            raise UpdateFailed("Unable to connect to the ORVIBO cloud") from err

        await self._refresh_devices_from_cloud()
        self.gateway_manager = GatewayManager(
            self.username,
            self.password,
            self._gateway_ips,
            push_callback=self._on_status_update,
            state_callback=self._on_gateway_connectivity,
        )
        await self._connect_all_gateways()
        if self.gateway_manager is not None:
            await self.gateway_manager.start_monitoring()
        self._discover_task = self.hass.async_create_background_task(
            self._gateway_discover_loop(),
            name=f"{DOMAIN}_gateway_discovery",
        )

    async def _on_gateway_connectivity(
        self,
        gateway_uid: str,
        connected: bool,
    ) -> None:
        """Raise or dismiss a persistent notification on gateway link changes."""

        if self._closed:
            return
        host = self._gateway_ips.get(gateway_uid) or gateway_uid
        notification_id = f"{DOMAIN}_gateway_{mask_identifier(gateway_uid)}"
        if connected:
            persistent_notification.async_dismiss(self.hass, notification_id)
            _LOGGER.info("ORVIBO gateway %s reconnected", mask_host(host))
            return
        persistent_notification.async_create(
            self.hass,
            f"ORVIBO 网关 {mask_host(host)} 连接已断开，正在自动重连。"
            "期间命令下发与状态同步可能暂时不可用。",
            title="ORVIBO 网关断连",
            notification_id=notification_id,
        )
        _LOGGER.warning("ORVIBO gateway %s disconnected; auto-reconnecting", mask_host(host))

    async def _async_setup(self) -> None:
        """Compatibility wrapper for older callers."""

        await self.async_setup()

    async def _async_update_data(self) -> dict[str, dict[str, object]]:
        """Refresh cloud snapshots and keep gateway endpoints current."""

        try:
            await self._refresh_devices_from_cloud()
            if self.gateway_manager is not None:
                await self.gateway_manager.async_update_cloud_gateways(self._gateway_ips)
            await self._connect_all_gateways()
        except CloudAuthenticationError as err:
            raise ConfigEntryAuthFailed("ORVIBO cloud authentication expired") from err
        except OrviboLanError as err:
            raise UpdateFailed("Unable to update ORVIBO devices") from err
        return self.device_states

    async def _refresh_devices_from_cloud(self) -> None:
        """Fetch and merge a cloud snapshot through StateStore."""

        refresh_timestamp = time.monotonic()
        (
            devices,
            statuses,
            _gateways,
            rooms,
            gateway_ips,
            _resolver,
        ) = await self.cloud_client.fetch_devices()
        normalized = normalize_readtable_devices(
            devices,
            statuses,
            set(gateway_ips),
        )
        if len(normalized) > _MAX_DEVICES:
            _LOGGER.warning(
                "Cloud returned %s devices; limiting the entry to %s",
                len(normalized),
                _MAX_DEVICES,
            )
            normalized = normalized[:_MAX_DEVICES]

        new_devices: dict[str, dict[str, object]] = {}
        for raw_device in normalized:
            device_id = str(raw_device["deviceId"])
            new_devices[device_id] = dict(raw_device)

        if not new_devices:
            self._state_store = None
            self.devices = {}
            self.device_types = {}
            self.room_names = {
                str(room["roomId"]): str(room.get("roomName") or "")
                for room in rooms
                if room.get("roomId") not in (None, "")
            }
            self._gateway_ips = dict(gateway_ips)
            self._sync_public_states()
            return

        self._ensure_state_store(set(new_devices))
        store = self._state_store
        if store is None:
            raise UpdateFailed("ORVIBO cloud returned no supported devices")
        store.retain_devices(new_devices)

        self._cloud_generation += 1
        for device_id in new_devices:
            raw_state = statuses.get(device_id, {})
            values = dict(raw_state)
            values.setdefault("deviceId", device_id)
            self._parse_sensor_state(values, device_id, new_devices)
            store.apply(
                StateUpdate(
                    device_id=device_id,
                    values=values,
                    source=StateSource.CLOUD,
                    monotonic=refresh_timestamp,
                    generation=self._cloud_generation,
                )
            )

        self.devices = new_devices
        self.device_types = {
            device_id: normalize_device_type(device.get("deviceType"))
            for device_id, device in new_devices.items()
        }
        self.room_names = {
            str(room["roomId"]): str(room.get("roomName") or "")
            for room in rooms
            if room.get("roomId") not in (None, "")
        }
        self._gateway_ips = dict(gateway_ips)
        self._sync_public_states()

    def _ensure_state_store(self, device_ids: set[str]) -> None:
        """Create the store once and extend its device whitelist in place."""

        if not device_ids:
            return
        if self._state_store is None:
            self._state_store = StateStore(device_ids)
            return

        self._state_store.add_devices(device_ids)

    async def _connect_all_gateways(self) -> None:
        """Warm known connections without making one gateway block the entry."""

        manager = self.gateway_manager
        if manager is None:
            return
        results = await asyncio.gather(
            *(manager.ensure(uid) for uid in self._gateway_ips),
            return_exceptions=True,
        )
        for uid, result in zip(self._gateway_ips, results):
            if isinstance(result, BaseException):
                reason = (
                    result.reason
                    if isinstance(result, GatewayConnectionError)
                    else type(result).__name__
                )
                _LOGGER.debug(
                    "Gateway %s is not ready (reason=%s)",
                    self._masked_device_id(uid),
                    reason,
                )
            else:
                _LOGGER.debug(
                    "Gateway %s connection ready (connected=%s)",
                    self._masked_device_id(uid),
                    result.connected,
                )

    async def _gateway_discover_loop(self) -> None:
        """Periodically ask GatewayManager to validate discovery candidates."""

        try:
            while not self._closed:
                await asyncio.sleep(GATEWAY_DISCOVER_INTERVAL.total_seconds())
                manager = self.gateway_manager
                if manager is None:
                    continue
                try:
                    await manager.discover()
                except (OrviboLanError, OSError) as err:
                    if not self._closed:
                        _LOGGER.debug("Gateway discovery failed (%s)", type(err).__name__)
        except asyncio.CancelledError:
            raise

    async def _on_status_update(
        self,
        gateway_uid: str,
        payload: Mapping[str, object],
    ) -> None:
        """Merge one cmd=42 update received by the manager-owned reader."""

        fields = tuple(sorted(str(key) for key in payload if not str(key).startswith("__")))
        command = self._payload_command(payload.get("cmd"))
        if command is None:
            _LOGGER.debug(
                "Dropped LAN state from gateway %s with invalid command %r",
                self._masked_device_id(gateway_uid),
                command,
            )
            return
        if command != CMD_STATE_UPDATE:
            _LOGGER.debug(
                "Validating compatibility LAN state command %r from gateway %s",
                command,
                self._masked_device_id(gateway_uid),
            )
        device_id = self._payload_device_id(payload)
        if device_id is None:
            _LOGGER.debug(
                "Dropped LAN state from gateway %s without a device ID (cmd=%r, fields=%s)",
                self._masked_device_id(gateway_uid),
                command,
                fields,
            )
            return
        store = self._state_store
        if store is None or device_id not in store.device_ids:
            _LOGGER.debug(
                "Ignoring LAN state for unknown device %s (cmd=%r, fields=%s)",
                self._masked_device_id(device_id),
                command,
                fields,
            )
            return

        device = self.devices.get(device_id)
        expected_gateway = device.get("uid") if device is not None else None
        if not isinstance(expected_gateway, str) or expected_gateway != gateway_uid:
            _LOGGER.debug(
                "Ignoring LAN state for device %s from wrong gateway %s",
                self._masked_device_id(device_id),
                self._masked_device_id(gateway_uid),
            )
            return
        payload_gateway = self._payload_gateway_uid(payload)
        if payload_gateway is not None and payload_gateway != gateway_uid:
            _LOGGER.debug(
                "Ignoring LAN state for device %s with mismatched gateway metadata",
                self._masked_device_id(device_id),
            )
            return
        if not self._valid_lan_state_payload(payload):
            _LOGGER.debug(
                "Rejected malformed LAN state for device %s (fields=%s)",
                self._masked_device_id(device_id),
                fields,
            )
            return

        values = {
            str(key): value
            for key, value in payload.items()
            if not str(key).startswith("__") and value is not None
        }
        values.pop("deviceID", None)
        values.pop("device_id", None)
        for field in _LAN_METADATA_FIELDS:
            values.pop(field, None)
        values["deviceId"] = device_id
        self._lan_generation += 1
        try:
            changed = store.apply(
                StateUpdate(
                    device_id=device_id,
                    values=values,
                    source=StateSource.LAN,
                    monotonic=time.monotonic(),
                    generation=self._lan_generation,
                )
            )
        except StateStoreError as err:
            _LOGGER.debug(
                "Rejected LAN state for device %s: %s",
                self._masked_device_id(device_id),
                err,
            )
            return
        if not changed:
            _LOGGER.debug(
                "LAN state unchanged for device %s (cmd=%r, fields=%s)",
                self._masked_device_id(device_id),
                command,
                fields,
            )
            return

        self._sync_public_states(notify=False)
        _LOGGER.debug(
            "Applied LAN state for device %s (cmd=%r, fields=%s)",
            self._masked_device_id(device_id),
            command,
            fields,
        )
        if self._notify_task is not None and not self._notify_task.done():
            self._notify_task.cancel()
        self._notify_task = self.hass.async_create_background_task(
            self._debounced_notify(),
            name=f"{DOMAIN}_state_notify",
        )

    @staticmethod
    def _payload_device_id(payload: Mapping[str, object]) -> str | None:
        """Return a normalized device identifier used by known firmware variants."""

        for field in ("deviceId", "deviceID", "device_id"):
            value = payload.get(field)
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                continue
            device_id = str(value).strip()
            if device_id:
                return device_id
        return None

    @staticmethod
    def _payload_command(value: object) -> int | None:
        """Normalize a protocol command without accepting booleans."""

        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return None
        return None

    @staticmethod
    def _payload_gateway_uid(payload: Mapping[str, object]) -> str | None:
        for field in ("gatewayUid", "gatewayUID", "uid"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _valid_lan_state_payload(payload: Mapping[str, object]) -> bool:
        """Reject malformed state values before they reach entity state."""

        properties = payload.get("properties")
        if properties is not None and not isinstance(properties, Mapping):
            return False
        if _DERIVED_STATE_FIELDS.intersection(payload):
            return False
        for field in _STATE_NUMBER_FIELDS.intersection(payload):
            value = payload[field]
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                return False
            try:
                number = int(str(value).strip())
            except ValueError:
                return False
            if not _STATE_NUMBER_MIN <= number <= _STATE_NUMBER_MAX:
                return False
        return True

    @staticmethod
    def _masked_device_id(device_id: str) -> str:
        """Return a stable, privacy-safe identifier for diagnostics."""

        return mask_identifier(device_id)

    async def async_control_device(
        self,
        device_id: str,
        payload: Mapping[str, object],
    ) -> bool:
        """Send a command and raise HomeAssistantError for every failed control."""

        device = self.devices.get(device_id)
        if device is None:
            raise HomeAssistantError(f"Unknown ORVIBO device: {self._masked_device_id(device_id)}")
        if device.get("_orvibo_read_only") or device.get("_orvibo_status_only"):
            raise HomeAssistantError(
                f"ORVIBO device {self._masked_device_id(device_id)} is read-only"
            )
        uid_value = device.get("uid")
        if not isinstance(uid_value, str) or not uid_value:
            raise HomeAssistantError(
                f"ORVIBO device {self._masked_device_id(device_id)} has no gateway"
            )
        manager = self.gateway_manager
        if manager is None or self._closed:
            raise HomeAssistantError("ORVIBO gateway manager is unavailable")

        try:
            response = await manager.send(
                uid_value,
                payload,
                timeout=_CONTROL_TIMEOUT,
            )
        except (OrviboLanError, KeyError) as err:
            raise HomeAssistantError(
                f"Failed to control ORVIBO device {self._masked_device_id(device_id)}"
            ) from err
        status = response.get("status")
        if status != 0:
            status_text = (
                status if isinstance(status, int) and not isinstance(status, bool) else "invalid"
            )
            raise HomeAssistantError(
                "ORVIBO device "
                f"{self._masked_device_id(device_id)} rejected the command "
                f"(status={status_text})"
            )
        return True

    async def async_send_raw(
        self,
        device_id: str,
        payload: Mapping[str, object],
    ) -> bool:
        """Compatibility alias using the same correlated request path."""

        return await self.async_control_device(device_id, payload)

    async def async_cleanup(self) -> None:
        """Cancel coordinator tasks before closing all manager-owned transports."""

        if self._closed:
            return
        self._closed = True
        tasks = (self._discover_task, self._notify_task)
        self._discover_task = None
        self._notify_task = None
        for task in tasks:
            if task is not None and not task.done():
                task.cancel()
        for task in tasks:
            if task is not None:
                with suppress(asyncio.CancelledError, Exception):
                    await task
        manager, self.gateway_manager = self.gateway_manager, None
        try:
            if manager is not None:
                await manager.close()
        finally:
            self._state_store = None
        self.devices.clear()
        self.device_states.clear()
        self.device_types.clear()
        self.room_names.clear()
        self._gateway_ips.clear()

    def get_device_state(self, device_id: str) -> dict[str, object] | None:
        """Return a detached mutable state view for entity compatibility."""

        state = self.device_states.get(device_id)
        return dict(state) if state is not None else None

    def is_device_available(self, device_id: str) -> bool:
        """Resolve availability from the transport that owns the device."""

        device = self.devices.get(device_id)
        if device is None:
            return False
        if device.get("_orvibo_read_only"):
            return bool(getattr(self, "last_update_success", True))
        uid = device.get("uid")
        manager = self.gateway_manager
        return bool(
            isinstance(uid, str) and uid and manager is not None and manager.is_connected(uid)
        )

    def get_room_name(self, device_id: str) -> str | None:
        """Return the cloud room name assigned to a device."""

        device = self.devices.get(device_id)
        if device is None:
            return None
        room_id = device.get("roomId")
        if room_id not in (None, ""):
            room_name = self.room_names.get(str(room_id))
            if room_name:
                return room_name
        state = self.get_device_state(device_id) or {}
        descriptor = state_properties(state).get("Descriptor")
        if isinstance(descriptor, Mapping):
            state_room_id = descriptor.get("roomId")
            if state_room_id not in (None, ""):
                return self.room_names.get(str(state_room_id))
        device_room_name = device.get("roomName")
        return str(device_room_name) if device_room_name not in (None, "") else None

    def _sync_public_states(self, *, notify: bool = True) -> None:
        store = self._state_store
        if store is None:
            self.device_states = {}
            return
        states: dict[str, dict[str, object]] = {}
        for device_id, snapshot in store.snapshot_all().items():
            state = dict(snapshot.values)
            self._parse_sensor_state(state, device_id, self.devices)
            states[device_id] = state
        self.device_states = states
        if notify:
            self.async_set_updated_data(states)

    def _parse_sensor_state(
        self,
        state: dict[str, object],
        device_id: str,
        devices: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        """Derive stable sensor fields without changing protocol payloads."""

        source_devices = devices if devices is not None else self.devices
        device = source_devices.get(device_id, {})
        device_type = normalize_device_type(device.get("deviceType"))

        def integer(value: object) -> int | None:
            if value is None or isinstance(value, bool):
                return None
            try:
                return int(str(value))
            except (TypeError, ValueError):
                return None

        value1 = integer(state.get("value1"))
        value2 = integer(state.get("value2"))
        value3 = integer(state.get("value3"))
        value4 = integer(state.get("value4"))
        if device_type == 46 and value1 is not None:
            state["door_state"] = value1 == 1
        elif device_type == 26 and value3 is not None:
            state["motion_detected"] = value3 == 1
        elif device_type == 27 and value1 is not None:
            state["smoke_detected"] = value1 == 1
        elif device_type == 25 and value1 is not None:
            state["gas_detected"] = value1 == 1
        elif device_type == 54 and value1 is not None:
            state["water_leak_detected"] = value1 == 1
        elif device_type == 56 and value1 is not None:
            state["emergency_state"] = value1 == 1
        if value4 is not None and 0 <= value4 <= 100:
            state["battery"] = value4
        if device_type in (22, 23):
            if value1 is not None:
                state["temperature"] = float(value1)
            if value2 is not None:
                state["humidity"] = float(value2)

        properties = state_properties(state)
        battery = property_percentage(properties, PROPERTY_BATTERY_POWER)
        if battery is not None:
            state["battery"] = battery
        door_open = property_switch_state(properties, PROPERTY_DOOR_STATUS)
        if door_open is not None:
            state["property_door_open"] = door_open

    async def _debounced_notify(self) -> None:
        try:
            await asyncio.sleep(0.2)
            self.async_set_updated_data(self.device_states)
            _LOGGER.debug(
                "Published LAN state update to Home Assistant (devices=%s)",
                len(self.device_states),
            )
        except asyncio.CancelledError:
            raise
