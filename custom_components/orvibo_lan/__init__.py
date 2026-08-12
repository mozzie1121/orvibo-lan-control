"""ORVIBO LAN  integration lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_FAMILY_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    HIDDEN_TYPES,
    MANUFACTURER,
    PLATFORMS,
    SERVICE_REFRESH_DEVICES,
)
from .coordinator import OrviboLanCoordinator
from .selection import config_entry_unique_id, selected_device_ids

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OrviboLanRuntimeData:
    """Resources owned by one config entry."""

    coordinator: OrviboLanCoordinator
    remove_options_listener: Callable[[], None]
    remove_start_listener: Callable[[], None] | None = None


def get_runtime_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> OrviboLanRuntimeData:
    """Read runtime_data with a hass.data fallback for HA2024.1."""

    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, OrviboLanRuntimeData):
        return runtime
    return hass.data[DOMAIN][entry.entry_id]


def _set_runtime_data(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: OrviboLanRuntimeData,
) -> None:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    try:
        entry.runtime_data = runtime
    except AttributeError:
        # ConfigEntry.runtime_data is unavailable on HA2024.1.
        pass


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate selections and scope account identities to one family."""

    if entry.version > 3:
        return False
    if entry.version == 3:
        return True

    data = dict(entry.data)
    options = dict(entry.options)
    legacy_selection = data.pop("selected_device_ids", None)
    if "selected_device_ids" not in options and isinstance(legacy_selection, (list, tuple, set)):
        options["selected_device_ids"] = [str(item) for item in legacy_selection]
    update: dict[str, object] = {
        "data": data,
        "options": options,
        "version": 3,
    }
    family_id = data.get(CONF_FAMILY_ID)
    current_unique_id = getattr(entry, "unique_id", None)
    if (
        entry.version < 3
        and isinstance(current_unique_id, str)
        and current_unique_id
        and isinstance(family_id, str)
        and family_id
    ):
        update["unique_id"] = config_entry_unique_id(
            current_unique_id,
            family_id,
        )
    hass.config_entries.async_update_entry(entry, **update)
    return True


def _register_services(hass: HomeAssistant) -> None:
    """Register domain services once for all loaded entries."""

    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_DEVICES):
        return

    async def async_refresh_devices(_call: ServiceCall) -> None:
        runtimes = tuple(hass.data.get(DOMAIN, {}).values())
        await asyncio.gather(
            *(
                runtime.coordinator.async_request_refresh()
                for runtime in runtimes
                if hasattr(runtime, "coordinator")
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_DEVICES,
        async_refresh_devices,
    )


def _unregister_services_if_unused(hass: HomeAssistant) -> None:
    """Remove domain services after the final config entry unloads."""

    if hass.data.get(DOMAIN):
        return
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_DEVICES):
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH_DEVICES)


def _schedule_area_assignment(
    hass: HomeAssistant,
    entry: ConfigEntry,
    runtime: OrviboLanRuntimeData,
    event: Event,
) -> None:
    """Schedule area assignment safely from an event-bus callback thread."""

    # ``async_listen_once`` removes itself after invoking the callback. Avoid
    # trying to remove the same listener again during config-entry unload.
    runtime.remove_start_listener = None
    hass.add_job(_async_assign_areas, hass, entry, event)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one config entry and all entity platforms."""

    coordinator = OrviboLanCoordinator(
        hass,
        async_get_clientsession(hass),
        str(entry.data[CONF_USERNAME]),
        str(entry.data[CONF_PASSWORD]),
        str(entry.data[CONF_FAMILY_ID]) if entry.data.get(CONF_FAMILY_ID) else None,
    )
    try:
        await coordinator.async_setup()
    except ConfigEntryAuthFailed:
        await coordinator.async_cleanup()
        raise
    except Exception as err:
        await coordinator.async_cleanup()
        raise ConfigEntryNotReady("Unable to initialize ORVIBO LAN") from err

    remove_options_listener = entry.add_update_listener(_async_options_updated)
    runtime = OrviboLanRuntimeData(coordinator, remove_options_listener)
    _set_runtime_data(hass, entry, runtime)
    _register_services(hass)
    platforms_forwarded = False
    try:
        _register_devices(hass, entry, coordinator)
        platforms_forwarded = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        if hass.is_running:
            await _async_assign_areas(hass, entry)
        else:
            runtime.remove_start_listener = hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                lambda event: _schedule_area_assignment(hass, entry, runtime, event),
            )
    except Exception:
        if platforms_forwarded:
            with suppress(Exception):
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        if runtime.remove_start_listener is not None:
            with suppress(Exception):
                runtime.remove_start_listener()
            runtime.remove_start_listener = None
        with suppress(Exception):
            runtime.remove_options_listener()
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        _unregister_services_if_unused(hass)
        try:
            entry.runtime_data = None
        except AttributeError:
            pass
        with suppress(Exception):
            await coordinator.async_cleanup()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms before releasing their shared runtime resources."""

    runtime = get_runtime_data(hass, entry)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False
    if runtime.remove_start_listener is not None:
        runtime.remove_start_listener()
        runtime.remove_start_listener = None
    runtime.remove_options_listener()
    await runtime.coordinator.async_cleanup()
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    _unregister_services_if_unused(hass)
    try:
        entry.runtime_data = None
    except AttributeError:
        pass
    return True


async def _async_options_updated(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload entities when the selected device set changes."""

    await hass.config_entries.async_reload(entry.entry_id)


def _register_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: OrviboLanCoordinator,
) -> None:
    from homeassistant.helpers import device_registry as dr

    registry = dr.async_get(hass)
    for gateway_uid in coordinator._gateway_ips:
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"gateway_{gateway_uid}")},
            manufacturer=MANUFACTURER,
            name="Orvibo Gateway",
            model="MixPad",
        )

    selected = selected_device_ids(entry.options, coordinator.devices)
    for device_id, device in coordinator.devices.items():
        device_type = coordinator.device_types.get(device_id, 0)
        if device_id not in selected or device_type in HIDDEN_TYPES or device_type in (114, 510):
            continue
        info: dict[str, object] = {
            "config_entry_id": entry.entry_id,
            "identifiers": {(DOMAIN, f"device_{device_id}")},
            "manufacturer": MANUFACTURER,
            "name": device.get("deviceName") or f"ORVIBO {device_id[-6:]}",
            "model": device.get("model") or str(device_type or "Unknown"),
        }
        device_uid = device.get("uid")
        if isinstance(device_uid, str) and device_uid and device.get("_orvibo_lan_capable"):
            info["via_device"] = (DOMAIN, f"gateway_{device_uid}")
        registry.async_get_or_create(**info)


async def _async_assign_areas(
    hass: HomeAssistant,
    entry: ConfigEntry,
    _event: Event | None = None,
) -> None:
    """Assign registered devices to their cloud room after HA starts."""

    runtime = get_runtime_data(hass, entry)
    coordinator = runtime.coordinator
    from homeassistant.helpers import area_registry as ar
    from homeassistant.helpers import device_registry as dr

    area_registry = ar.async_get(hass)
    device_registry = dr.async_get(hass)
    for device_id, device in coordinator.devices.items():
        if coordinator.device_types.get(device_id, 0) in (114, 510):
            continue
        room_name = coordinator.get_room_name(device_id)
        if not room_name:
            continue
        area = area_registry.async_get_area_by_name(room_name)
        if area is None:
            area = area_registry.async_create(room_name)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, f"device_{device_id}")}
        )
        if device_entry is not None and device_entry.area_id != area.id:
            device_registry.async_update_device(device_entry.id, area_id=area.id)
