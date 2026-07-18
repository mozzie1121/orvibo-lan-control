"""Orvibo LAN Cover 平台（窗帘）。"""

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
    from homeassistant.components.cover import CoverEntity, CoverDeviceClass

    class OrviboLanCover(CoordinatorEntity, CoverEntity):
        """Orvibo 窗帘实体。"""

        _attr_has_entity_name = True

        def __init__(self, coordinator, device_id, device):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            name = device.get("deviceName", f"Cover {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_cover_{device_id}"
            self._attr_name = name
            self._attr_device_class = CoverDeviceClass.CURTAIN

            # 绑定到网关设备
            uid = device.get("uid", "")
            if uid:
                self._attr_device_info = {
                    "identifiers": {(DOMAIN, f"gateway_{uid}")},
                    "name": f"Orvibo Gateway",
                    "manufacturer": MANUFACTURER,
                    "model": "MixPad",
                    "sw_version": "1.0",
                    "connections": {("uid", uid)},
                }

        def _parse_position(self, st: dict) -> Optional[int]:
            """解析窗帘位置。cmd=42: value1=0关100开，跟 HA 一致，直接返回。"""
            v1 = st.get("value1")
            if v1 is not None:
                pos = int(v1)
                return max(0, min(pos, 100))
            return None

        @property
        def is_closed(self) -> Optional[bool]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            pos = self._parse_position(st)
            if pos is not None:
                return pos <= 5
            return None

        @property
        def current_cover_position(self) -> Optional[int]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            return self._parse_position(st)

        async def async_open_cover(self, **kwargs):
            payload = dc.cover_open(self._device_id, self._device.get("uid", ""),
                                    self.coordinator.username)
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

        async def async_close_cover(self, **kwargs):
            payload = dc.cover_close(self._device_id, self._device.get("uid", ""),
                                     self.coordinator.username)
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

        async def async_stop_cover(self, **kwargs):
            payload = dc.cover_stop(self._device_id, self._device.get("uid", ""),
                                    self.coordinator.username)
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

        async def async_set_cover_position(self, position: int, **kwargs):
            payload = dc.cover_position(self._device_id, self._device.get("uid", ""),
                                        position, self.coordinator.username)
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    from .const import HIDDEN_TYPES

    for did, device in coordinator.devices.items():
        dt = coordinator.device_types.get(did, 0)
        if dt != 34:
            continue
        if dt in HIDDEN_TYPES:
            continue

        entities.append(OrviboLanCover(coordinator, did, device))

    if entities:
        async_add_entities(entities)
