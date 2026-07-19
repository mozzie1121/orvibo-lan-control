"""Device selection helper for Orvibo LAN Control config entries.

参照 orvibohomebridge 的 selection.py，支持用户在配置流程中选择要暴露的设备。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

CONF_SELECTED_DEVICE_IDS = "selected_device_ids"


def selected_device_ids(
    options: Mapping[str, Any],
    available_device_ids: Iterable[str],
) -> set[str]:
    """返回用户选择的设备 ID，默认（旧配置）返回全部可用设备。"""
    available = {str(device_id) for device_id in available_device_ids}
    if CONF_SELECTED_DEVICE_IDS not in options:
        return available
    configured = options.get(CONF_SELECTED_DEVICE_IDS)
    if not isinstance(configured, (list, tuple, set)):
        return set()
    return {str(device_id) for device_id in configured} & available


def device_is_selected(options: Mapping[str, Any], device_id: str) -> bool:
    """检查某个设备是否被选中。"""
    if CONF_SELECTED_DEVICE_IDS not in options:
        return True
    configured = options.get(CONF_SELECTED_DEVICE_IDS)
    if not isinstance(configured, (list, tuple, set)):
        return False
    selected = {str(value) for value in configured}
    return str(device_id) in selected
