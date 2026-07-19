"""Tests for selection helpers (port of orvibohomebridge test_selection)."""

import sys
import os
import importlib.util

# Load module directly (no HA dependency)
_orvibo_lan = os.path.join(os.path.dirname(__file__), "..")
_mod_path = os.path.join(_orvibo_lan, "custom_components", "orvibo_lan", "selection.py")
_spec = importlib.util.spec_from_file_location(
    "custom_components.orvibo_lan.selection", _mod_path
)
_selection = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_selection)


def test_selected_device_ids_default_all():
    """旧配置无 selected_device_ids 时返回全部可用设备。"""
    available = {"dev1", "dev2", "dev3"}
    result = _selection.selected_device_ids({}, available)
    assert result == available


def test_selected_device_ids_filters():
    """配置了 selected_device_ids 时只返回交集。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: ["dev1", "dev2", "dev99"]}
    available = {"dev1", "dev2", "dev3"}
    result = _selection.selected_device_ids(options, available)
    assert result == {"dev1", "dev2"}


def test_selected_device_ids_empty_configured():
    """配置的 selected_device_ids 为空则返回空集。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: []}
    available = {"dev1", "dev2"}
    result = _selection.selected_device_ids(options, available)
    assert result == set()


def test_selected_device_ids_invalid_type():
    """配置的 selected_device_ids 不是 list 则返回空集。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: "not_a_list"}
    result = _selection.selected_device_ids(options, {"dev1"})
    assert result == set()


def test_device_is_selected_default_true():
    """旧配置无 selected_device_ids 时默认返回 True。"""
    assert _selection.device_is_selected({}, "dev1") is True


def test_device_is_selected_configured():
    """配置了 selected_device_ids 时检查是否在列表中。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: ["dev1", "dev2"]}
    assert _selection.device_is_selected(options, "dev1") is True
    assert _selection.device_is_selected(options, "dev3") is False


def test_device_is_selected_empty():
    """空列表时返回 False。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: []}
    assert _selection.device_is_selected(options, "dev1") is False


def test_device_is_selected_invalid_type():
    """不是 list 时返回 False。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: None}
    assert _selection.device_is_selected(options, "dev1") is False


def test_device_id_string_vs_int():
    """字符串与数字 IDs 可互换使用。"""
    options = {_selection.CONF_SELECTED_DEVICE_IDS: ["123", "456"]}
    available = {123, 456, 789}
    result = _selection.selected_device_ids(options, available)
    assert result == {"123", "456"}

    assert _selection.device_is_selected(options, "123") is True
    assert _selection.device_is_selected(options, 123) is True
