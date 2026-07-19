"""Orvibo LAN 二元传感器平台。

支持设备类型：
- 26: 人体传感器 → 人体检测
- 46: 门窗传感器 → 门磁状态
- 25: 可燃气体探测器 → 燃气检测
- 27: 烟雾传感器 → 烟雾检测
- 54: 水浸探测器 → 水浸
- 56: 紧急按钮 → 紧急按钮状态
"""

import logging
from typing import Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrviboLanCoordinator

_LOGGER = logging.getLogger(__name__)


class OrviboLanBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """二元传感器基类。"""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator, device_id: str, device: dict,
        state_key: str, device_class: BinarySensorDeviceClass,
        name: str, icon: str, model: str,
    ):
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        self._state_key = state_key
        self._attr_unique_id = f"{DOMAIN}_binary_{state_key}_{device_id}"
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_icon = icon

        uid = device.get("uid", "")
        dev_info = {
            "identifiers": {(DOMAIN, f"device_{device_id}")},
            "name": device.get("deviceName", f"Sensor {device_id[:8]}"),
            "manufacturer": MANUFACTURER,
            "model": model,
            "sw_version": "1.0",
        }
        if uid:
            dev_info["via_device"] = (DOMAIN, f"gateway_{uid}")
        self._attr_device_info = dev_info

    @property
    def is_on(self) -> Optional[bool]:
        state = self.coordinator.get_device_state(self._device_id)
        return state.get(self._state_key, False) if state else False

    @property
    def available(self) -> bool:
        state = self.coordinator.get_device_state(self._device_id)
        return state.get("online", True) if state else True


# ── sensor 类型 → binary sensor 实体工厂 ──

_BINARY_SENSOR_FACTORIES = {
    26: [{
        "state_key": "motion_detected",
        "device_class": BinarySensorDeviceClass.MOTION,
        "name": "人体检测",
        "icon": "mdi:motion-sensor",
        "model": "Motion Sensor",
    }],
    46: [{
        "state_key": "door_state",
        "device_class": BinarySensorDeviceClass.DOOR,
        "name": "门磁状态",
        "icon": "mdi:door-open",
        "model": "Door Window Sensor",
    }],
    25: [{
        "state_key": "gas_detected",
        "device_class": BinarySensorDeviceClass.GAS,
        "name": "燃气检测",
        "icon": "mdi:gas-cylinder",
        "model": "Gas Sensor",
    }],
    27: [{
        "state_key": "smoke_detected",
        "device_class": BinarySensorDeviceClass.SMOKE,
        "name": "烟雾检测",
        "icon": "mdi:smoke-detector",
        "model": "Smoke Sensor",
    }],
    54: [{
        "state_key": "water_leak_detected",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "name": "水浸",
        "icon": "mdi:water",
        "model": "Water Leak Sensor",
    }],
    56: [{
        "state_key": "emergency_state",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "name": "紧急按钮",
        "icon": "mdi:alert-octagon",
        "model": "Emergency Button",
    }],
}

_BINARY_SENSOR_TYPES = set(_BINARY_SENSOR_FACTORIES.keys())


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """设置二元传感器实体。"""
    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    from .selection import selected_device_ids
    selected_ids = selected_device_ids(entry.options, coordinator.devices)
    entities = []

    for did, device in coordinator.devices.items():
        if did not in selected_ids:
            continue
        dt = coordinator.device_types.get(did, 0)
        if dt not in _BINARY_SENSOR_TYPES:
            continue

        for cfg in _BINARY_SENSOR_FACTORIES[dt]:
            entities.append(OrviboLanBinarySensorBase(
                coordinator, did, device,
                state_key=cfg["state_key"],
                device_class=cfg["device_class"],
                name=cfg["name"],
                icon=cfg["icon"],
                model=cfg["model"],
            ))

    if entities:
        async_add_entities(entities)
