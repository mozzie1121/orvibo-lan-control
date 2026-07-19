"""Orvibo LAN Sensor 平台（传感器）。

支持设备类型：
- 22/23: 温湿度传感器 → 温度 + 湿度 + 电量
- 25: 可燃气体探测器 → 电量
- 26: 人体传感器 → 电量
- 27: 烟雾传感器 → 电量
- 46: 门窗传感器 → 电量
- 54: 水浸探测器 → 电量
- 56: 紧急按钮 → 电量
- 300: 门锁/温湿度 → 温度+湿度+电量
- 522/107: 门锁 → 干电池电量 + 锂电池电量
"""

import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrviboLanCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_battery(state: dict) -> Optional[int]:
    """从设备状态中获取电量值（兼容多种字段名）。"""
    for key in ("battery", "batteryLevel", "powerLevel"):
        val = state.get(key)
        if val is not None:
            try:
                return int(float(val))
            except (TypeError, ValueError):
                pass
    # 部分设备用 value4 表示电量
    val4 = state.get("value4")
    if val4 is not None:
        try:
            v = int(float(val4))
            if 0 <= v <= 100:
                return v
        except (TypeError, ValueError):
            pass
    return None


def _get_value(state: dict, key: str) -> Optional[float]:
    """获取设备状态的数值字段。"""
    val = state.get(key)
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            pass
    return None


def _device_name(device: dict, device_id: str) -> str:
    return device.get("deviceName", f"Sensor {device_id[:8]}")


def _device_info(
    coordinator, device_id: str, device: dict, model: str
) -> dict:
    """构建 HA device_info。"""
    uid = device.get("uid", "")
    info = {
        "identifiers": {(DOMAIN, f"device_{device_id}")},
        "name": _device_name(device, device_id),
        "manufacturer": MANUFACTURER,
        "model": model,
        "sw_version": "1.0",
    }
    if uid:
        info["via_device"] = (DOMAIN, f"gateway_{uid}")
    return info


# ── 基类 ──


class OrviboLanBatterySensor(CoordinatorEntity, SensorEntity):
    """通用电池传感器基类。"""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator, device_id: str, device: dict,
        model: str, unique_suffix: str = "battery",
    ):
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        self._attr_unique_id = f"{DOMAIN}_{unique_suffix}_{device_id}"
        self._attr_name = "电量"
        self._attr_device_info = _device_info(
            coordinator, device_id, device, model,
        )

    @property
    def native_value(self) -> Optional[int]:
        return _get_battery(self.coordinator.get_device_state(self._device_id) or {})


# ── 温湿度传感器（22/23）──


class OrviboLanTemperatureSensor(CoordinatorEntity, SensorEntity):
    """温度传感器（type=22/23）。"""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, device_id: str, device: dict):
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        name = _device_name(device, device_id)
        self._attr_unique_id = f"{DOMAIN}_temperature_{device_id}"
        self._attr_name = f"{name} 温度"
        self._attr_device_info = _device_info(
            coordinator, device_id, device, "Orvibo Temp/Humidity Sensor",
        )

    @property
    def native_value(self) -> Optional[float]:
        st = self.coordinator.get_device_state(self._device_id)
        if not st:
            return None
        return _get_value(st, "temperature") or _get_value(st, "value1")


class OrviboLanHumiditySensor(CoordinatorEntity, SensorEntity):
    """湿度传感器（type=22/23）。"""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, device_id: str, device: dict):
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        name = _device_name(device, device_id)
        self._attr_unique_id = f"{DOMAIN}_humidity_{device_id}"
        self._attr_name = f"{name} 湿度"
        self._attr_device_info = _device_info(
            coordinator, device_id, device, "Orvibo Temp/Humidity Sensor",
        )

    @property
    def native_value(self) -> Optional[float]:
        st = self.coordinator.get_device_state(self._device_id)
        if not st:
            return None
        return _get_value(st, "humidity") or _get_value(st, "value2")


# ── 门锁（522/107）──


class OrviboLanDryBatterySensor(OrviboLanBatterySensor):
    """门锁干电池电量。"""

    def __init__(self, coordinator, device_id: str, device: dict):
        super().__init__(
            coordinator, device_id, device,
            model="Orvibo Door Lock",
            unique_suffix="dry_battery",
        )
        self._attr_name = "干电池电量"

    @property
    def native_value(self) -> Optional[int]:
        st = self.coordinator.get_device_state(self._device_id)
        if st:
            val = st.get("dry_battery_level") or _get_battery(st)
            if val is not None:
                return int(val)
        return None


class OrviboLanLithiumBatterySensor(OrviboLanBatterySensor):
    """门锁锂电池电量。"""

    def __init__(self, coordinator, device_id: str, device: dict):
        super().__init__(
            coordinator, device_id, device,
            model="Orvibo Door Lock",
            unique_suffix="lithium_battery",
        )
        self._attr_name = "锂电池电量"

    @property
    def native_value(self) -> Optional[int]:
        st = self.coordinator.get_device_state(self._device_id)
        if st:
            val = st.get("lithium_battery_level") or _get_battery(st)
            if val is not None:
                return int(val)
        return None


# ── sensor 类型 → 实体工厂 ──

_SENSOR_FACTORIES = {
    # (type, model, 实体列表)
    22: ("Orvibo Temp/Humidity Sensor", lambda c, did, d: [
        OrviboLanTemperatureSensor(c, did, d),
        OrviboLanHumiditySensor(c, did, d),
        OrviboLanBatterySensor(c, did, d, "Orvibo Temp/Humidity Sensor", f"th_battery_{did}"),
    ]),
    23: ("Orvibo Temp/Humidity Sensor", lambda c, did, d: [
        OrviboLanTemperatureSensor(c, did, d),
        OrviboLanHumiditySensor(c, did, d),
        OrviboLanBatterySensor(c, did, d, "Orvibo Temp/Humidity Sensor", f"th_battery_{did}"),
    ]),
    25: ("Orvibo Gas Sensor", lambda c, did, d: [
        OrviboLanBatterySensor(c, did, d, "Orvibo Gas Sensor", f"gas_battery_{did}"),
    ]),
    26: ("Orvibo Motion Sensor", lambda c, did, d: [
        OrviboLanBatterySensor(c, did, d, "Orvibo Motion Sensor", f"motion_battery_{did}"),
    ]),
    27: ("Orvibo Smoke Sensor", lambda c, did, d: [
        OrviboLanBatterySensor(c, did, d, "Orvibo Smoke Sensor", f"smoke_battery_{did}"),
    ]),
    46: ("Orvibo Door/Window Sensor", lambda c, did, d: [
        OrviboLanBatterySensor(c, did, d, "Orvibo Door/Window Sensor", f"door_battery_{did}"),
    ]),
    54: ("Orvibo Water Leak Sensor", lambda c, did, d: [
        OrviboLanBatterySensor(c, did, d, "Orvibo Water Leak Sensor", f"water_battery_{did}"),
    ]),
    56: ("Orvibo Emergency Button", lambda c, did, d: [
        OrviboLanBatterySensor(c, did, d, "Orvibo Emergency Button", f"emergency_battery_{did}"),
    ]),
    300: ("Orvibo Sensor", lambda c, did, d: [
        OrviboLanTemperatureSensor(c, did, d),
        OrviboLanHumiditySensor(c, did, d),
        OrviboLanBatterySensor(c, did, d, "Orvibo Sensor", f"th_battery_{did}"),
    ]),
    522: ("Orvibo Door Lock", lambda c, did, d: [
        OrviboLanDryBatterySensor(c, did, d),
        OrviboLanLithiumBatterySensor(c, did, d),
    ]),
    107: ("Orvibo Door Lock", lambda c, did, d: [
        OrviboLanDryBatterySensor(c, did, d),
        OrviboLanLithiumBatterySensor(c, did, d),
    ]),
}

_SENSOR_TYPES = set(_SENSOR_FACTORIES.keys())


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """设置传感器实体。"""
    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    from .selection import selected_device_ids
    selected_ids = selected_device_ids(entry.options, coordinator.devices)
    entities = []

    for did, device in coordinator.devices.items():
        if did not in selected_ids:
            continue
        dt = coordinator.device_types.get(did, 0)
        if dt not in _SENSOR_TYPES:
            continue

        factory = _SENSOR_FACTORIES[dt][1]
        entities.extend(factory(coordinator, did, device))

    if entities:
        async_add_entities(entities)
