"""Tests for centralized device profiles and readtable normalization."""

from custom_components.orvibo_lan.device_profiles import (
    PROPERTY_BATTERY_POWER,
    PROPERTY_DOOR_STATUS,
    light_color_mode,
    normalize_readtable_devices,
    platforms_for_device,
    property_percentage,
    property_switch_state,
    verified_profile_name,
)
from custom_components.orvibo_lan.profiles import is_status_only_type
from custom_components.orvibo_lan.lib import device_control
from custom_components.orvibo_lan.lib.device_control import (
    fan_off,
    fan_on,
    fan_set_speed,
    power_only_light,
)


def test_control_serials_are_unique_across_a_burst() -> None:
    payloads = [device_control.power_only_light("device", "gateway", True) for _ in range(100)]

    assert len({payload["serial"] for payload in payloads}) == 100
    assert len({payload["uniSerial"] for payload in payloads}) == 100


def test_door_locks_are_status_only_and_never_controllable() -> None:
    """门锁（107/300/522）只有状态能力，不允许下发控制命令。"""

    assert is_status_only_type(107)
    assert is_status_only_type(300)
    assert is_status_only_type(522)
    assert not is_status_only_type(0)
    assert not is_status_only_type(38)

    normalized = normalize_readtable_devices(
        [
            {
                "deviceId": "lock-522",
                "deviceType": 522,
                "uid": "gateway-1",
                "deviceName": "Zigbee 门锁",
            }
        ],
        {},
        {"gateway-1"},
    )
    assert normalized
    assert normalized[0]["_orvibo_lan_capable"] is True
    assert normalized[0]["_orvibo_status_only"] is True


def test_property_light_brightness_profiles_share_wire_shape() -> None:
    payload_502 = device_control.light_brightness("device", "gateway", 502, 128)
    payload_503 = device_control.light_brightness("device", "gateway", 503, 128)
    for payload in (payload_502, payload_503):
        payload.pop("serial")
        payload.pop("uniSerial")

    assert payload_502 == payload_503


def test_power_only_light_profile_uses_onoff_mode():
    device = {"deviceType": 1, "subDeviceType": 1}
    assert light_color_mode(device) == "onoff"
    assert verified_profile_name(device) == "power_only_light"


def test_power_only_light_command_keeps_brightness_zero():
    turn_on = power_only_light("device", "gateway", True, "user")
    turn_off = power_only_light("device", "gateway", False, "user")
    assert (turn_on["order"], turn_on["value1"], turn_on["value2"]) == (
        "on",
        0,
        0,
    )
    assert (turn_off["order"], turn_off["value1"], turn_off["value2"]) == (
        "off",
        1,
        0,
    )


def test_ventilation_percentage_maps_to_protocol_presets():
    assert fan_on("device", "gateway", 516)["value1"] == 100
    assert fan_off("device", "gateway", 516)["value1"] == 50
    assert fan_set_speed("device", "gateway", 516, 25)["value1"] == 0
    assert fan_set_speed("device", "gateway", 516, 75)["value1"] == 100


def test_verified_tunable_light_profiles():
    assert (
        verified_profile_name(
            {
                "deviceType": 38,
                "subDeviceType": 6,
            }
        )
        == "tunable_light"
    )
    assert (
        verified_profile_name(
            {
                "deviceType": 503,
                "subDeviceType": 436,
                "model": "294339fdc9b04613bb6cf1569305b78c",
            }
        )
        == "property_tunable_light"
    )


def test_property_helpers_accept_scalar_and_nested_shapes():
    assert property_switch_state({PROPERTY_DOOR_STATUS: "open"}, PROPERTY_DOOR_STATUS)
    assert not property_switch_state(
        {PROPERTY_DOOR_STATUS: {"status": "off"}},
        PROPERTY_DOOR_STATUS,
    )
    assert (
        property_percentage(
            {PROPERTY_BATTERY_POWER: {"power": 76}},
            PROPERTY_BATTERY_POWER,
        )
        == 76
    )
    assert (
        property_percentage(
            {PROPERTY_BATTERY_POWER: 101},
            PROPERTY_BATTERY_POWER,
        )
        is None
    )


def test_status_only_property_device_is_retained_without_becoming_a_light():
    statuses = {
        "lock-001": {
            "deviceId": "lock-001",
            "uid": "cloud-lock-uid",
            "pdid": "ORBSTDA-030830-UVEUH,IISNJM",
            "properties": {
                PROPERTY_BATTERY_POWER: 80,
                PROPERTY_DOOR_STATUS: "off",
            },
        },
    }

    result = normalize_readtable_devices([], statuses, {"mixpad-uid"})

    assert len(result) == 1
    device = result[0]
    assert device["_orvibo_status_only"] is True
    assert device["_orvibo_read_only"] is True
    assert device["uid"] == ""
    assert platforms_for_device(device, statuses["lock-001"]) == frozenset(
        {
            "binary_sensor",
            "sensor",
        }
    )


def test_non_gateway_device_requires_supported_read_only_properties():
    devices = [
        {
            "deviceId": "wifi-device",
            "uid": "wifi-uid",
            "deviceType": 52,
        }
    ]
    assert (
        normalize_readtable_devices(
            devices,
            {"wifi-device": {"deviceId": "wifi-device"}},
            {"mixpad-uid"},
        )
        == []
    )


def test_unknown_mixpad_child_is_retained_for_device_registry():
    devices = [
        {
            "deviceId": "unknown-child",
            "uid": "mixpad-uid",
            "deviceType": 999,
            "deviceName": "Unknown child",
        }
    ]
    result = normalize_readtable_devices(devices, {}, {"mixpad-uid"})
    assert len(result) == 1
    assert result[0]["_orvibo_lan_capable"] is True
    assert platforms_for_device(result[0], {}) == frozenset()
