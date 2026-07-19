"""Orvibo LAN Sensor 平台（传感器）。"""

import logging
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, PERCENTAGE

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrviboLanCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """设置传感器实体。"""

    class OrviboLanTemperatureSensor(CoordinatorEntity, SensorEntity):
        """Orvibo 温度传感器。"""

        _attr_has_entity_name = True
        _attr_device_class = SensorDeviceClass.TEMPERATURE
        _attr_state_class = SensorStateClass.MEASUREMENT
        _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

        def __init__(self, coordinator, device_id, device):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            name = device.get("deviceName", f"Sensor {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_temperature_{device_id}"
            self._attr_name = f"{name} 温度"

            uid = device.get("uid", "")
            dev_info = {
                "identifiers": {(DOMAIN, f"device_{device_id}")},
                "name": device.get("deviceName", f"Sensor {device_id[:8]}"),
                "manufacturer": MANUFACTURER,
                "model": "Orvibo Temp/Humidity Sensor",
                "sw_version": "1.0",
            }
            if uid:
                dev_info["via_device"] = (DOMAIN, f"gateway_{uid}")
            self._attr_device_info = dev_info

        @property
        def native_value(self) -> Optional[float]:
            st = self.coordinator.get_device_state(self._device_id)
            if st:
                temp = st.get("value1")
                if temp is not None:
                    try:
                        return float(temp)
                    except (TypeError, ValueError):
                        pass
            return None

    class OrviboLanHumiditySensor(CoordinatorEntity, SensorEntity):
        """Orvibo 湿度传感器。"""

        _attr_has_entity_name = True
        _attr_device_class = SensorDeviceClass.HUMIDITY
        _attr_state_class = SensorStateClass.MEASUREMENT
        _attr_native_unit_of_measurement = PERCENTAGE

        def __init__(self, coordinator, device_id, device):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            name = device.get("deviceName", f"Sensor {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_humidity_{device_id}"
            self._attr_name = f"{name} 湿度"

            uid = device.get("uid", "")
            dev_info = {
                "identifiers": {(DOMAIN, f"device_{device_id}")},
                "name": device.get("deviceName", f"Sensor {device_id[:8]}"),
                "manufacturer": MANUFACTURER,
                "model": "Orvibo Temp/Humidity Sensor",
                "sw_version": "1.0",
            }
            if uid:
                dev_info["via_device"] = (DOMAIN, f"gateway_{uid}")
            self._attr_device_info = dev_info

        @property
        def native_value(self) -> Optional[float]:
            st = self.coordinator.get_device_state(self._device_id)
            if st:
                hum = st.get("value2")
                if hum is not None:
                    try:
                        return float(hum)
                    except (TypeError, ValueError):
                        pass
            return None

    coordinator: OrviboLanCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for did, device in coordinator.devices.items():
        dt = coordinator.device_types.get(did, 0)
        if dt not in (22, 23):
            continue

        entities.append(OrviboLanTemperatureSensor(coordinator, did, device))
        entities.append(OrviboLanHumiditySensor(coordinator, did, device))

    if entities:
        async_add_entities(entities)
