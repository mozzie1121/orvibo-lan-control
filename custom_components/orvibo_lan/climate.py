"""Orvibo LAN Climate 平台（空调）。"""

import logging
import time
from typing import Any, Optional, List

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
    from homeassistant.components.climate import (
        ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction,
        ATTR_TEMPERATURE, ATTR_FAN_MODE, ATTR_HVAC_MODE,
    )
    from homeassistant.const import UnitOfTemperature

    class OrviboLanClimate(CoordinatorEntity, ClimateEntity):
        """Orvibo 空调实体。"""

        _attr_has_entity_name = True

        def __init__(self, coordinator, device_id, device):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device

            name = device.get("deviceName", f"AC {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_climate_{device_id}"
            self._attr_name = name
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_target_temperature_step = 1.0
            self._attr_min_temp = 16.0
            self._attr_max_temp = 30.0
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT,
                                      HVACMode.FAN_ONLY, HVACMode.DRY]
            self._attr_fan_modes = ["auto", "low", "medium", "high"]

            # 每个设备独立注册为 HA 设备，via_device 指向网关
            uid = device.get("uid", "")
            dev_info = {
                "identifiers": {(DOMAIN, f"device_{device_id}")},
                "name": device.get("deviceName", f"AC {device_id[:8]}"),
                "manufacturer": MANUFACTURER,
                "model": "Orvibo AC",
                "sw_version": "1.0",
            }
            if uid:
                dev_info["via_device"] = (DOMAIN, f"gateway_{uid}")
            self._attr_device_info = dev_info
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE |
                ClimateEntityFeature.FAN_MODE
            )

        @property
        def hvac_mode(self) -> HVACMode:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return HVACMode.OFF
            return self._parse_hvac_mode(st)

        @property
        def hvac_action(self) -> HVACAction:
            mode = self.hvac_mode
            if mode == HVACMode.OFF:
                return HVACAction.OFF
            return HVACAction.COOLING if mode == HVACMode.COOL else HVACAction.IDLE

        @property
        def target_temperature(self) -> Optional[float]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            # value4 高16位=目标温度x100, 低16位=当前温度x100
            v4 = st.get("value4")
            if v4 is not None:
                try:
                    return float(int(v4) >> 16) / 100.0
                except (TypeError, ValueError):
                    return 25.0
            return 25.0

        @property
        def current_temperature(self) -> Optional[float]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            # value4 低16位=当前温度x100
            v4 = st.get("value4")
            if v4 is not None:
                try:
                    return float(int(v4) & 0xFFFF) / 100.0
                except (TypeError, ValueError):
                    return 25.0
            return 25.0

        @property
        def fan_mode(self) -> Optional[str]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            v3 = st.get("value3")
            if v3 is not None:
                v3i = int(v3)
                speeds = ["auto", "low", "medium", "high"]
                if 1 <= v3i <= 3:
                    return speeds[v3i]
            return "auto"

        def _parse_hvac_mode(self, st: dict) -> HVACMode:
            """解析空调模式。
            value1: 0=开 / 1=关
            value2: 2=除湿 / 3=制冷 / 4=制热 / 7=送风
            """
            v1 = st.get("value1")
            if v1 is None:
                return HVACMode.OFF
            v1 = int(v1)
            # 0 = 开机, 非0(1) = 关机
            if v1 != 0:
                return HVACMode.OFF
            v2 = st.get("value2")
            if v2 is None:
                return HVACMode.COOL  # 默认制冷
            v2 = int(v2)
            mode_map = {2: HVACMode.DRY, 3: HVACMode.COOL,
                        4: HVACMode.HEAT, 7: HVACMode.FAN_ONLY}
            return mode_map.get(v2, HVACMode.COOL)

        async def async_set_hvac_mode(self, hvac_mode):
            _LOGGER.debug("[AC] async_set_hvac_mode: %s", hvac_mode)
            uid = self._device.get("uid", "")
            
            if hvac_mode == "off":
                payload = dc.ac_off(self._device_id, uid, username=self.coordinator.username)
                _LOGGER.debug("[AC] 发关机: off")
                await self._send_ac(payload)
            else:
                mode_map = {"cool": 3, "heat": 4, "dry": 2, "fan_only": 7}
                mode_str = str(hvac_mode).split(".")[-1].lower() if "." in str(hvac_mode) else str(hvac_mode).lower()
                mode_val = mode_map.get(mode_str, 3)
                # 获取当前设备状态，传给 ac_on_with_mode 以继承温度/风速
                current_state = self.coordinator.get_device_state(self._device_id)
                payload = dc.ac_on_with_mode(self._device_id, uid, mode_val,
                                             username=self.coordinator.username,
                                             current_state=current_state)
                _LOGGER.debug("[AC] 发开机+模式: mode_val=%d", mode_val)
                await self._send_ac(payload)
            
            await self.coordinator.async_request_refresh()

        async def _send_ac(self, payload):
            """发空调命令，通过 send_control 读取网关回复。"""
            _LOGGER.debug("[AC] 发命令: order=%s, v1=%s, v2=%s",
                          payload.get("order"), payload.get("value1"), payload.get("value2"))
            ok = await self.coordinator.async_control_device(self._device_id, payload)
            _LOGGER.debug("[AC] 结果: %s", "成功" if ok else "失败")

        async def async_set_temperature(self, **kwargs):
            temp = kwargs.get("temperature")
            if temp is None:
                return
            current_state = self.coordinator.get_device_state(self._device_id)
            payload = dc.ac_set_temp(self._device_id, self._device.get("uid", ""),
                                     int(temp), username=self.coordinator.username,
                                     current_state=current_state)
            _LOGGER.debug("[AC] 发温度: temp=%d", int(temp))
            await self._send_ac(payload)
            await self.coordinator.async_request_refresh()

        async def async_set_fan_mode(self, fan_mode: str):
            speed_map = {"low": 1, "medium": 2, "high": 3}
            v3 = speed_map.get(fan_mode.lower(), 1)
            current_state = self.coordinator.get_device_state(self._device_id)
            payload = dc.ac_wind(self._device_id, self._device.get("uid", ""),
                                 v3, username=self.coordinator.username,
                                 current_state=current_state)
            _LOGGER.debug("[AC] 发风速: speed=%d", v3)
            await self._send_ac(payload)
            await self.coordinator.async_request_refresh()

    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    from .selection import selected_device_ids
    selected_ids = selected_device_ids(entry.options, coordinator.devices)
    entities = []

    from .const import HIDDEN_TYPES

    for did, device in coordinator.devices.items():
        if did not in selected_ids:
            continue
        dt = coordinator.device_types.get(did, 0)
        if dt not in (36, 81):
            continue
        if dt in HIDDEN_TYPES:
            continue

        entities.append(OrviboLanClimate(coordinator, did, device))

    if entities:
        async_add_entities(entities)
