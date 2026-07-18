"""Orvibo LAN Fan 平台（新风系统）。"""

import logging
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrviboLanCoordinator
from .lib import device_control as dc

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    # 延迟导入，避免 HA 2026 import_module 阻塞检测
    from homeassistant.components.fan import FanEntity, FanEntityFeature

    class OrviboLanFan(CoordinatorEntity, FanEntity):
        """Orvibo 新风实体。"""

        _attr_has_entity_name = True

        def __init__(self, coordinator, device_id, device, device_type):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            self._device_type = device_type

            name = device.get("deviceName", f"Fan {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_fan_{device_id}"
            self._attr_name = name
            self._attr_supported_features = (
                FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON |
                FanEntityFeature.TURN_OFF
            )
            self._attr_speed_count = 4  # low/medium/high/auto

            # 绑定到网关设备
            uid = device.get("uid", "")
            if uid:
                dev_info = {
                    "identifiers": {(DOMAIN, f"gateway_{uid}")},
                    "name": f"Orvibo Gateway",
                    "manufacturer": MANUFACTURER,
                    "model": "MixPad",
                    "sw_version": "1.0",
                    "connections": {("uid", uid)},
                }
                room_name = device.get("roomName") or device.get("room_name", "")
                if room_name:
                    dev_info["suggested_area"] = room_name
                self._attr_device_info = dev_info

        @property
        def is_on(self) -> bool:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return False
            return self._parse_on(st)

        @property
        def percentage(self) -> Optional[int]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            return self._parse_speed(st)

        def _parse_on(self, st: dict) -> bool:
            if self._device_type == 516:
                props = st.get("properties", {}) or {}
                onoff = props.get("onoff", {})
                if isinstance(onoff, dict):
                    return onoff.get("status") == "on"
                return False
            # type 81: value2 表示档位, >0 表示开启
            v2 = st.get("value2")
            if v2 is not None:
                return int(v2) > 0
            return False

        def _parse_speed(self, st: dict) -> Optional[int]:
            if self._device_type == 516:
                props = st.get("properties", {}) or {}
                fan_speed = props.get("fanSpeed", {})
                if isinstance(fan_speed, dict):
                    speed_value = fan_speed.get("value")
                    if speed_value is not None:
                        return int(speed_value) * 100 // 100
                return None
            # type 81: value2 = 0(off)/1(low)/2(mid)/3(high)
            v2 = st.get("value2")
            if v2 is not None:
                v2 = int(v2)
                if v2 == 0:
                    return 0
                return int(v2 * 100 / 3)
            return None

        async def async_turn_on(self, speed: Optional[str] = None,
                                 percentage: Optional[int] = None, **kwargs):
            if percentage is not None:
                await self.async_set_percentage(percentage)
            else:
                payload = dc.fan_on(
                    self._device_id, self._device.get("uid", ""),
                    self._device_type, username=self.coordinator.username,
                )
                await self.coordinator.async_control_device(self._device_id, payload)
                await self.coordinator.async_request_refresh()

        async def async_turn_off(self, **kwargs):
            payload = dc.fan_off(
                self._device_id, self._device.get("uid", ""),
                self._device_type, username=self.coordinator.username,
            )
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

        async def async_set_percentage(self, percentage: int):
            payload = dc.fan_set_speed(
                self._device_id, self._device.get("uid", ""),
                self._device_type, percentage,
                username=self.coordinator.username,
            )
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    from .const import HIDDEN_TYPES

    for did, device in coordinator.devices.items():
        dt = coordinator.device_types.get(did, 0)
        if dt not in (516, 81):
            continue
        if dt in HIDDEN_TYPES:
            continue

        entities.append(OrviboLanFan(coordinator, did, device, dt))

    if entities:
        async_add_entities(entities)
