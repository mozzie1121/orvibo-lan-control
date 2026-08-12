"""Central device capability profiles used by discovery and entities."""

from __future__ import annotations

from dataclasses import dataclass

PLATFORM_BINARY_SENSOR = "binary_sensor"
PLATFORM_CLIMATE = "climate"
PLATFORM_COVER = "cover"
PLATFORM_FAN = "fan"
PLATFORM_LIGHT = "light"
PLATFORM_SENSOR = "sensor"


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """Capabilities shared by config flow and entity platforms."""

    platforms: frozenset[str]
    status_only: bool = False


DEVICE_PROFILES: dict[int, DeviceProfile] = {
    0: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    1: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    22: DeviceProfile(frozenset({PLATFORM_SENSOR})),
    23: DeviceProfile(frozenset({PLATFORM_SENSOR})),
    25: DeviceProfile(frozenset({PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR})),
    26: DeviceProfile(frozenset({PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR})),
    27: DeviceProfile(frozenset({PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR})),
    34: DeviceProfile(frozenset({PLATFORM_COVER})),
    35: DeviceProfile(frozenset({PLATFORM_COVER})),
    36: DeviceProfile(frozenset({PLATFORM_CLIMATE})),
    38: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    46: DeviceProfile(frozenset({PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR})),
    54: DeviceProfile(frozenset({PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR})),
    56: DeviceProfile(frozenset({PLATFORM_SENSOR, PLATFORM_BINARY_SENSOR})),
    81: DeviceProfile(frozenset({PLATFORM_CLIMATE, PLATFORM_FAN})),
    102: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    107: DeviceProfile(frozenset({PLATFORM_SENSOR}), status_only=True),
    300: DeviceProfile(frozenset({PLATFORM_SENSOR}), status_only=True),
    501: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    502: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    503: DeviceProfile(frozenset({PLATFORM_LIGHT})),
    506: DeviceProfile(frozenset({PLATFORM_COVER})),
    516: DeviceProfile(frozenset({PLATFORM_FAN})),
    522: DeviceProfile(frozenset({PLATFORM_SENSOR}), status_only=True),
}


def platforms_for_type(device_type: int) -> frozenset[str]:
    """Return the declared platforms for one normalized device type."""

    profile = DEVICE_PROFILES.get(device_type)
    return profile.platforms if profile is not None else frozenset()


def is_status_only_type(device_type: int) -> bool:
    """Return whether a device type only reports state and cannot be controlled.

    门锁（107/300/522）只有状态获取/推送能力，没有控制能力，即使经
    MixPad 网关可达也不能下发控制命令。
    """

    profile = DEVICE_PROFILES.get(device_type)
    return bool(profile is not None and profile.status_only)
