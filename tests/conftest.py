"""包级别的 conftest：共享 fixture 和 mock。"""
import sys
import os

_test_root = os.path.dirname(os.path.abspath(__file__))
_orvibo_lan = os.path.join(_test_root, "..", "custom_components")
sys.path.insert(0, os.path.join(_test_root, ".."))

# Mock HA 依赖
import unittest.mock as mock

ha_modules = [
    "homeassistant", "homeassistant.core", "homeassistant.helpers",
    "homeassistant.exceptions", "homeassistant.helpers.update_coordinator",
    "homeassistant.const", "homeassistant.config_entries",
]
for name in ha_modules:
    sys.modules[name] = mock.MagicMock()

# 提供 FakeDataUpdateCoordinator
from typing import Dict, Any, Generic, TypeVar

_T = TypeVar('_T')

class FakeDataUpdateCoordinator(Generic[_T]):
    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data: _T = None
        self._listeners = []

    def async_set_updated_data(self, data: _T):
        self.data = data
        for listener in self._listeners:
            try:
                listener()
            except Exception:
                pass

    def async_add_listener(self, callback):
        self._listeners.append(callback)

sys.modules["homeassistant.helpers.update_coordinator"].DataUpdateCoordinator = FakeDataUpdateCoordinator
sys.modules["homeassistant.helpers.update_coordinator"].UpdateFailed = Exception
sys.modules["homeassistant.exceptions"].ConfigEntryAuthFailed = Exception

# 直接加载 const 模块（替换 mock）
import importlib.util
const_path = os.path.join(_orvibo_lan, "orvibo_lan", "const.py")
spec = importlib.util.spec_from_file_location("custom_components.orvibo_lan.const", const_path)
if spec and spec.loader:
    const_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(const_mod)
    sys.modules["custom_components.orvibo_lan.const"] = const_mod
