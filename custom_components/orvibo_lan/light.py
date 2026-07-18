"""Orvibo LAN Light 平台。
参考 orvibohomebridge 的成熟控制逻辑：
- 旧协议 (statusType=2): value1=onoff, value2=亮度, value3=色温(mired), order="on"/"fast color temperature"
- ThingModel (statusType=501/502/503): properties.onoff/brightness/colorTemp, order="set property"
"""
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
    38: "color_temp",          # 调光调色灯 (ZCL)
    102: "onoff",
    501: "onoff",              # ThingModel 开关
    502: "brightness",         # ThingModel 可调光
    503: "color_temp",         # ThingModel 色温灯带
    0: "brightness",           # 旧协议调光灯
    1: "color_temp",           # 旧协议色温灯
    2: "onoff",
}

# 色温上限/下限（开尔文）
COLOR_TEMP_RANGE = {
    "min": 2700,  # 370 mired
    "max": 6000,  # 167 mired
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    from homeassistant.components.light import LightEntity, ColorMode

    class OrviboLanLight(CoordinatorEntity, LightEntity):
        _attr_has_entity_name = True

        def __init__(self, coordinator, device_id, device, device_type):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            self._device_type = device_type

            name = device.get("deviceName", f"Light {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_light_{device_id}"
            self._attr_name = name

            # 每个设备独立注册为 HA 设备，via_device 指向网关
            uid = device.get("uid", "")
            dev_info = {
                "identifiers": {(DOMAIN, f"device_{device_id}")},
                "name": device.get("deviceName", f"Light {device_id[:8]}"),
                "manufacturer": MANUFACTURER,
                "model": "Orvibo Light",
                "sw_version": "1.0",
            }
            if uid:
                dev_info["via_device"] = (DOMAIN, f"gateway_{uid}")
            self._attr_device_info = dev_info

            cm_str = TYPE_COLOR_MODE_MAP.get(self._device_type, "onoff")
            if cm_str == "color_temp":
                self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_min_color_temp_kelvin = COLOR_TEMP_RANGE["min"]
                self._attr_max_color_temp_kelvin = COLOR_TEMP_RANGE["max"]
            elif cm_str == "brightness":
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
                self._attr_color_mode = ColorMode.BRIGHTNESS
            else:
                self._attr_supported_color_modes = {ColorMode.ONOFF}
                self._attr_color_mode = ColorMode.ONOFF

        def _get_st(self) -> Optional[dict]:
            return self.coordinator.get_device_state(self._device_id)

        def _is_thingmodel(self) -> bool:
            """是否是 ThingModel 协议（statusType=501/502/503 等）。"""
            return self._device_type in {501, 502, 503, 135, 136, 137, 143, 2, 554}

        def _is_old_protocol(self) -> bool:
            """是否是旧协议 (statusType=2, value1-4)。"""
            return self._device_type in {0, 1, 38}

        @property
        def is_on(self) -> bool:
            st = self._get_st()
            if not st:
                return False
            if self._is_thingmodel():
                props = st.get("properties", {}) or {}
                onoff = props.get("onoff", {})
                if isinstance(onoff, dict):
                    return onoff.get("status") == "on"
                return False
            # 旧协议: value1=0 开, value1=1 关
            v1 = st.get("value1")
            if v1 is not None:
                return int(v1) == 0
            return False

        @property
        def brightness(self) -> Optional[int]:
            st = self._get_st()
            if not st or not self.is_on:
                return None
            if self._is_thingmodel():
                props = st.get("properties", {}) or {}
                bri_obj = props.get("brightness", {})
                if isinstance(bri_obj, dict):
                    pct = bri_obj.get("percent")
                    if pct is not None:
                        return int(pct) * 255 // 100
                return None
            # 旧协议: value2 = 亮度 0-255
            v2 = st.get("value2")
            if v2 is not None:
                return max(0, min(int(v2), 255))
            return None

        @property
        def color_temp_kelvin(self) -> Optional[int]:
            """返回开尔文色温。"""
            st = self._get_st()
            if not st or not self.is_on:
                return None
            if self._is_thingmodel() and self._device_type == 503:
                props = st.get("properties", {}) or {}
                ct_obj = props.get("colorTemp", {})
                if isinstance(ct_obj, dict):
                    kelvin = ct_obj.get("value")
                    if kelvin:
                        return int(kelvin)
                return None
            # 旧协议: value3 = 色温 (mireds)
            v3 = st.get("value3")
            if v3 is not None:
                v3 = int(v3)
                if 150 <= v3 <= 400:
                    # mired → Kelvin
                    return 1000000 // v3
            return None

        @property
        def color_temp(self) -> Optional[int]:
            """返回 mireds（HA 旧版兼容）。"""
            kelvin = self.color_temp_kelvin
            if kelvin:
                return 1000000 // kelvin
            return None

        async def async_turn_on(self, **kwargs):
            brightness_ha = kwargs.get("brightness")  # 0-255
            ct_kelvin = kwargs.get("color_temp_kelvin")
            ct_mired = kwargs.get("color_temp")

            # 统一转换为开尔文
            if ct_kelvin is None and ct_mired is not None and ct_mired > 0:
                ct_kelvin = 1000000 // ct_mired

            uid = self._device.get("uid", "")

            if brightness_ha is not None and ct_kelvin is not None:
                # 同时设置亮度和色温 → 用 order="on" 一次性下发
                payload = dc.light_on_off(
                    self._device_id, uid,
                    self._device_type,
                    True,  # power on
                    brightness=brightness_ha,
                    color_temp_k=ct_kelvin,
                    username=self.coordinator.username,
                )
            elif brightness_ha is not None:
                payload = dc.light_brightness(
                    self._device_id, uid,
                    self._device_type,
                    brightness_ha,
                    self.coordinator.username,
                )
            elif ct_kelvin is not None:
                payload = dc.light_colortemp(
                    self._device_id, uid,
                    self._device_type,
                    ct_kelvin,
                    username=self.coordinator.username,
                )
            else:
                payload = dc.light_on(
                    self._device_id, uid,
                    self._device_type,
                    self.coordinator.username,
                )

            await self.coordinator.async_control_device(self._device_id, payload)

        async def async_turn_off(self, **kwargs):
            uid = self._device.get("uid", "")
            payload = dc.light_off(
                self._device_id, uid,
                self._device_type,
                self.coordinator.username,
            )
            await self.coordinator.async_control_device(self._device_id, payload)

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
