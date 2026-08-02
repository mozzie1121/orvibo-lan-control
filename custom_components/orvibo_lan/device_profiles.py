"""Device profiles and readtable normalization for ORVIBO devices."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from .profiles import is_status_only_type, platforms_for_type

PROPERTY_DOOR_STATUS = "door_status"
PROPERTY_BATTERY_POWER = "battery_power"
READ_ONLY_PROPERTIES = frozenset({PROPERTY_DOOR_STATUS, PROPERTY_BATTERY_POWER})

VERIFIED_PROPERTY_LIGHT_MODELS = frozenset(
    {
        "294339fdc9b04613bb6cf1569305b78c",
        "71b94d0309094d1e9c678e4c21bbf878",
        "f731c19a484c419282051494ceecd66a",
    }
)


def normalize_device_type(value: Any) -> int:
    """Return a numeric device type, or zero for an invalid value."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def normalize_sub_device_type(value: Any) -> str:
    """Normalize sub-device types for profile matching."""
    return "" if value in (None, "") else str(value).strip()


def state_properties(state: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a state's property mapping."""
    if not isinstance(state, Mapping):
        return {}
    properties = state.get("properties")
    return properties if isinstance(properties, Mapping) else {}


def property_value(properties: Mapping[str, Any], key: str) -> Any:
    """Extract scalar values from both cloud and ThingModel property shapes."""
    value = properties.get(key)
    if not isinstance(value, Mapping):
        return value
    for nested_key in ("value", "power", "status", "percent"):
        if nested_key in value:
            return value[nested_key]
    return None


def property_switch_state(properties: Mapping[str, Any], key: str) -> Optional[bool]:
    """Normalize an on/off property."""
    value = property_value(properties, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "on", "open"}:
            return True
        if normalized in {"0", "false", "off", "closed"}:
            return False
    return None


def property_percentage(properties: Mapping[str, Any], key: str) -> Optional[int]:
    """Normalize a percentage property and reject invalid values."""
    value = property_value(properties, key)
    if isinstance(value, bool):
        return None
    try:
        percentage = int(float(value))
    except (TypeError, ValueError):
        return None
    return percentage if 0 <= percentage <= 100 else None


def platforms_for_device(
    device: Mapping[str, Any],
    state: Mapping[str, Any] | None = None,
) -> frozenset[str]:
    """Return all HA platforms supported by a device profile."""
    raw_device_type = device.get("deviceType")
    platforms: set[str] = set()
    if raw_device_type not in (None, ""):
        platforms.update(platforms_for_type(normalize_device_type(raw_device_type)))
    properties = state_properties(state)
    if PROPERTY_DOOR_STATUS in properties:
        platforms.add("binary_sensor")
    if PROPERTY_BATTERY_POWER in properties:
        platforms.add("sensor")
    return frozenset(platforms)


def supports_platform(
    device: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    platform: str,
) -> bool:
    """Return whether a normalized device supports one HA platform."""
    return platform in platforms_for_device(device, state)


def light_color_mode(device: Mapping[str, Any]) -> str:
    """Return the HA light capability for a verified or compatible profile."""
    device_type = normalize_device_type(device.get("deviceType"))
    sub_type = normalize_sub_device_type(device.get("subDeviceType"))

    # Captured relay endpoints expose power only even when their broad type is a light.
    if device_type in {1, 102} and sub_type == "1":
        return "onoff"
    if device_type in {501, 102}:
        return "onoff"
    if device_type in {0, 502}:
        return "brightness"
    if device_type in {1, 38, 503}:
        return "color_temp"
    return "onoff"


def verified_profile_name(device: Mapping[str, Any]) -> str:
    """Return a stable profile name useful in diagnostics and tests."""
    device_type = normalize_device_type(device.get("deviceType"))
    sub_type = normalize_sub_device_type(device.get("subDeviceType"))
    model = str(device.get("model") or "").strip()

    if device_type in {1, 102} and sub_type == "1":
        return "power_only_light"
    if device_type == 38 and sub_type in {"4", "6", "13"}:
        return "tunable_light"
    if device_type == 503 and sub_type == "436" and model in VERIFIED_PROPERTY_LIGHT_MODELS:
        return "property_tunable_light"
    return "legacy_type_profile"


def _first_text(item: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _has_read_only_capability(state: Mapping[str, Any] | None) -> bool:
    return bool(READ_ONLY_PROPERTIES.intersection(state_properties(state)))


def normalize_readtable_devices(
    devices: list[dict[str, Any]],
    statuses: Mapping[str, Mapping[str, Any]],
    gateway_uids: set[str],
) -> list[dict[str, Any]]:
    """Filter LAN devices and retain property-capable status-only devices."""
    normalized: dict[str, dict[str, Any]] = {}

    for raw in devices:
        if not isinstance(raw, Mapping) or raw.get("delFlag") in (1, "1"):
            continue
        device_id = _first_text(raw, ("deviceId", "deviceID"))
        if not device_id:
            continue
        state = statuses.get(device_id)
        device_uid = _first_text(raw, ("uid",))
        lan_capable = bool(device_uid and device_uid in gateway_uids)
        read_only_capable = _has_read_only_capability(state)

        # Preserve the existing LAN rule, with a narrow exception for useful
        # property-based devices whose state comes from the cloud snapshot.
        if device_uid and not lan_capable and not read_only_capable:
            continue

        device = dict(raw)
        device["deviceId"] = device_id
        raw_device_type = device.get("deviceType")
        device["deviceType"] = (
            normalize_device_type(raw_device_type) if raw_device_type not in (None, "") else None
        )
        device["_orvibo_lan_capable"] = lan_capable
        device["_orvibo_read_only"] = not lan_capable
        device["_orvibo_status_only"] = (
            is_status_only_type(normalize_device_type(raw_device_type))
            if raw_device_type not in (None, "")
            else False
        )
        normalized[device_id] = device

    for device_id, state in statuses.items():
        if (
            device_id in normalized
            or not isinstance(state, Mapping)
            or state.get("delFlag") in (1, "1")
            or not _has_read_only_capability(state)
        ):
            continue

        source_uid = _first_text(state, ("uid",))
        lan_capable = bool(source_uid and source_uid in gateway_uids)
        model = _first_text(
            state,
            (
                "model",
                "modelName",
                "modelId",
                "modelID",
                "pdid",
            ),
        )
        normalized[device_id] = {
            "deviceId": device_id,
            "uid": source_uid if lan_capable else "",
            "sourceUid": source_uid,
            "deviceName": _first_text(
                state,
                ("deviceName", "devName", "name", "nickName", "nickname"),
            )
            or model
            or f"ORVIBO {device_id[-6:]}",
            "model": model,
            "deviceType": (
                normalize_device_type(state.get("deviceType"))
                if state.get("deviceType") not in (None, "")
                else None
            ),
            "subDeviceType": normalize_sub_device_type(
                state.get("subDeviceType", state.get("subDevType")),
            ),
            "roomId": _first_text(state, ("roomId", "roomID")),
            "_orvibo_lan_capable": lan_capable,
            "_orvibo_read_only": not lan_capable,
            "_orvibo_status_only": True,
        }

    return list(normalized.values())
