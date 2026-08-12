"""Shared lightweight Home Assistant stubs for unit tests."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from collections.abc import Callable
from enum import Enum, IntFlag
from typing import Generic, TypeVar
from unittest.mock import MagicMock

_TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
_CUSTOM_COMPONENTS = os.path.join(_TEST_ROOT, "..", "custom_components")
sys.path.insert(0, os.path.join(_TEST_ROOT, ".."))


def _package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


homeassistant = _package("homeassistant")
_package("homeassistant.helpers")

for module_name in (
    "homeassistant.helpers.area_registry",
    "homeassistant.helpers.device_registry",
):
    sys.modules[module_name] = MagicMock()

core = types.ModuleType("homeassistant.core")
exceptions = types.ModuleType("homeassistant.exceptions")
ha_const = types.ModuleType("homeassistant.const")
config_entries = types.ModuleType("homeassistant.config_entries")
data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
for module in (
    core,
    exceptions,
    ha_const,
    config_entries,
    data_entry_flow,
    entity_platform,
):
    sys.modules[module.__name__] = module


class FakeHomeAssistantError(Exception):
    """Base Home Assistant service error used by tests."""


class FakeConfigEntryAuthFailed(Exception):
    """Authentication error used by coordinator tests."""


class FakeConfigFlow:
    """Minimal ConfigFlow surface for production-path unit tests."""

    def __init_subclass__(cls, *, domain: str | None = None, **kwargs) -> None:
        del kwargs
        cls.domain = domain

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    async def async_set_unique_id(self, unique_id: str) -> None:
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        return None

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}


class FakeOptionsFlow:
    @property
    def config_entry(self):
        """Match Home Assistant's read-only OptionsFlow property."""

        return None

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_show_menu(self, **kwargs):
        return {"type": "menu", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}


class FakeCoordinatorEntity:
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator


class StringEnum(str, Enum):
    pass


class FeatureFlag(IntFlag):
    FIRST = 1
    SECOND = 2
    THIRD = 4


core.Event = object
core.HomeAssistant = object
core.ServiceCall = object
exceptions.ConfigEntryAuthFailed = FakeConfigEntryAuthFailed
exceptions.ConfigEntryNotReady = type("ConfigEntryNotReady", (Exception,), {})
exceptions.HomeAssistantError = FakeHomeAssistantError
config_entries.ConfigEntry = object
config_entries.ConfigFlow = FakeConfigFlow
config_entries.OptionsFlow = FakeOptionsFlow
data_entry_flow.FlowResult = dict
entity_platform.AddEntitiesCallback = Callable
ha_const.EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"
ha_const.PERCENTAGE = "%"
ha_const.UnitOfTemperature = type(
    "UnitOfTemperature",
    (),
    {"CELSIUS": "°C"},
)
homeassistant.config_entries = config_entries


aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client.async_get_clientsession = MagicMock(return_value=MagicMock())
sys.modules[aiohttp_client.__name__] = aiohttp_client

update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
_T = TypeVar("_T")


class FakeDataUpdateCoordinator(Generic[_T]):
    """Small coordinator contract used by the existing unit tests."""

    def __init__(self, hass, logger, name: str, update_interval) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data: _T | None = None
        self._listeners: list[Callable[[], None]] = []

    def async_set_updated_data(self, data: _T) -> None:
        self.data = data
        for listener in self._listeners:
            listener()

    def async_add_listener(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)


update_coordinator.DataUpdateCoordinator = FakeDataUpdateCoordinator
update_coordinator.CoordinatorEntity = FakeCoordinatorEntity
update_coordinator.UpdateFailed = Exception
sys.modules[update_coordinator.__name__] = update_coordinator

selector = MagicMock()
selector.SelectSelectorMode.LIST = "list"
sys.modules["homeassistant.helpers.selector"] = selector

components = _package("homeassistant.components")


def component_module(name: str) -> types.ModuleType:
    module = types.ModuleType(f"homeassistant.components.{name}")
    sys.modules[module.__name__] = module
    setattr(components, name, module)
    return module


sensor = component_module("sensor")
sensor.SensorDeviceClass = type(
    "SensorDeviceClass",
    (),
    {"BATTERY": "battery", "TEMPERATURE": "temperature", "HUMIDITY": "humidity"},
)
sensor.SensorStateClass = type("SensorStateClass", (), {"MEASUREMENT": "measurement"})
sensor.SensorEntity = type("SensorEntity", (), {})

binary_sensor = component_module("binary_sensor")
binary_sensor.BinarySensorDeviceClass = type(
    "BinarySensorDeviceClass",
    (),
    {
        "MOTION": "motion",
        "DOOR": "door",
        "GAS": "gas",
        "SMOKE": "smoke",
        "MOISTURE": "moisture",
        "PROBLEM": "problem",
    },
)
binary_sensor.BinarySensorEntity = type("BinarySensorEntity", (), {})

light = component_module("light")
light.LightEntity = type("LightEntity", (), {})
light.ColorMode = type(
    "ColorMode",
    (),
    {"COLOR_TEMP": "color_temp", "BRIGHTNESS": "brightness", "ONOFF": "onoff"},
)

cover = component_module("cover")
cover.ATTR_POSITION = "position"
cover.ATTR_TILT_POSITION = "tilt_position"
cover.CoverDeviceClass = type(
    "CoverDeviceClass",
    (),
    {"SHUTTER": "shutter", "CURTAIN": "curtain"},
)
cover.CoverEntity = type("CoverEntity", (), {})
cover.CoverEntityFeature = type(
    "CoverEntityFeature",
    (),
    {
        "OPEN": 1,
        "CLOSE": 2,
        "STOP": 4,
        "SET_POSITION": 8,
        "SET_TILT_POSITION": 16,
    },
)

fan = component_module("fan")
fan.FanEntity = type("FanEntity", (), {})
fan.FanEntityFeature = type(
    "FanEntityFeature",
    (),
    {"SET_SPEED": 1, "TURN_ON": 2, "TURN_OFF": 4},
)

climate = component_module("climate")
climate.ClimateEntity = type("ClimateEntity", (), {})
climate.ClimateEntityFeature = type(
    "ClimateEntityFeature",
    (),
    {"TARGET_TEMPERATURE": 1, "FAN_MODE": 2},
)
climate.HVACMode = type(
    "HVACMode",
    (),
    {
        "OFF": "off",
        "COOL": "cool",
        "HEAT": "heat",
        "FAN_ONLY": "fan_only",
        "DRY": "dry",
    },
)
climate.HVACAction = type(
    "HVACAction",
    (),
    {"OFF": "off", "COOLING": "cooling", "HEATING": "heating", "FAN": "fan"},
)

# Load const directly so tests get real domain constants instead of MagicMock values.
const_path = os.path.join(_CUSTOM_COMPONENTS, "orvibo_lan", "const.py")
spec = importlib.util.spec_from_file_location(
    "custom_components.orvibo_lan.const",
    const_path,
)
if spec is not None and spec.loader is not None:
    const_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(const_module)
    sys.modules["custom_components.orvibo_lan.const"] = const_module
