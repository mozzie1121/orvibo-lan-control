"""Orvibo LAN Light 平台。"""

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

# 设备类型 → 支持的 color_mode（字符串标记，运行时替换为 ColorMode 常量）
TYPE_COLOR_MODE_MAP = {
    38: "color_temp",
    102: "onoff",
    501: "onoff",
    502: "brightness",
    503: "color_temp",
    0: "brightness",
    1: "color_temp",
    2: "onoff",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    # 延迟导入，避免 HA 2026 的 import_module 阻塞检测
    from homeassistant.components.light import LightEntity, ColorMode

    # 创建一个动态子类，继承 CoordinatorEntity + LightEntity
    class OrviboLanLight(CoordinatorEntity, LightEntity):
        """Orvibo 灯实体。"""

        _attr_has_entity_name = True

        def __init__(self, coordinator, device_id, device, device_type):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            self._device_type = device_type

            name = device.get("deviceName", f"Light {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_light_{device_id}"
            self._attr_name = name

            cm_str = TYPE_COLOR_MODE_MAP.get(self._device_type, "onoff")
            if cm_str == "color_temp":
                self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_min_mireds = 154
                self._attr_max_mireds = 370
            elif cm_str == "brightness":
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
                self._attr_color_mode = ColorMode.BRIGHTNESS
            else:
                self._attr_supported_color_modes = {ColorMode.ONOFF}
                self._attr_color_mode = ColorMode.ONOFF

        @property
        def is_on(self) -> bool:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return False
            return self._parse_state(st)

        @property
        def brightness(self) -> Optional[int]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            return self._parse_brightness(st)

        @property
        def color_temp(self) -> Optional[int]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            return self._parse_color_temp(st)

        def _parse_state(self, st: dict) -> bool:
            _LOGGER.warning(f"[灯状态] device_type={self._device_type}, st={st}")
            if self._device_type in {501, 502, 503, 135, 136, 137, 143, 2, 554}:
                props = st.get("properties", {}) or {}
                onoff = props.get("onoff", {})
                if isinstance(onoff, dict):
                    return onoff.get("status") == "on"
                return False
            v1 = st.get("value1")
            if v1 is not None:
                return int(v1) == 0
            return False

        def _parse_brightness(self, st: dict) -> Optional[int]:
            if self._device_type in {502, 503}:
                props = st.get("properties", {}) or {}
                bri_obj = props.get("brightness", {})
                if isinstance(bri_obj, dict):
                    pct = bri_obj.get("percent")
                    if pct is not None:
                        return int(pct) * 255 // 100
                return None
            v2 = st.get("value2")
            if v2 is not None:
                return int(v2)
            return None

        def _parse_color_temp(self, st: dict) -> Optional[int]:
            if self._device_type == 503:
                props = st.get("properties", {}) or {}
                ct_obj = props.get("colorTemp", {})
                if isinstance(ct_obj, dict):
                    kelvin = ct_obj.get("value")
                    if kelvin:
                        return 1000000 // int(kelvin)
                return None
            v3 = st.get("value3")
            if v3 is not None:
                v3 = int(v3)
                if 150 <= v3 <= 400:
                    return v3
            return None

        async def async_turn_on(self, **kwargs):
            brightness = kwargs.get("brightness")
            ct_mired = kwargs.get("color_temp")

            if brightness is not None:
                bri_255 = int(brightness * 255 / 255)
                payload = dc.light_brightness(
                    self._device_id,
                    self._device.get("uid", ""),
                    self._device_type,
                    bri_255,
                    self.coordinator.username,
                )
            elif ct_mired is not None:
                kelvin = 1000000 // ct_mired
                payload = dc.light_colortemp(
                    self._device_id,
                    self._device.get("uid", ""),
                    self._device_type,
                    kelvin,
                    username=self.coordinator.username,
                )
            else:
                payload = dc.light_on(
                    self._device_id,
                    self._device.get("uid", ""),
                    self._device_type,
                    self.coordinator.username,
                )

            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

        async def async_turn_off(self, **kwargs):
            payload = dc.light_off(
                self._device_id,
                self._device.get("uid", ""),
                self._device_type,
                self.coordinator.username,
            )
            await self.coordinator.async_control_device(self._device_id, payload)
            await self.coordinator.async_request_refresh()

    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    from .const import HIDDEN_TYPES

    for did, device in coordinator.devices.items():
        dt = coordinator.device_types.get(did, 0)
        if dt not in (1, 38, 102, 501, 502, 503, 0):
            continue
        if dt in HIDDEN_TYPES:
            continue
        if dt == 114:
            continue

        entities.append(OrviboLanLight(coordinator, did, device, dt))

    if entities:
        async_add_entities(entities)
