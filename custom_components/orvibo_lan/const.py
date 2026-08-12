"""ORVIBO LAN  常量定义。"""

from datetime import timedelta

from .profiles import (
    DEVICE_PROFILES,
    PLATFORM_CLIMATE,
    PLATFORM_COVER,
    PLATFORM_FAN,
    PLATFORM_LIGHT,
    PLATFORM_SENSOR,
)

# ---- HA 配置键 ----
DOMAIN = "orvibo_lan"
MANUFACTURER = "ORVIBO"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_FAMILY_ID = "family_id"
CONF_SELECTED_DEVICE_IDS = "selected_device_ids"

SERVICE_REFRESH_DEVICES = "refresh_devices"

# ---- 更新间隔 ----
UPDATE_INTERVAL = timedelta(minutes=1)  # 补充只读属性设备的云端状态
GATEWAY_DISCOVER_INTERVAL = timedelta(minutes=5)  # UDP发现网关

# ---- 设备类型映射 ----
DEVICE_TYPE_COVER = PLATFORM_COVER
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_LIGHT = PLATFORM_LIGHT
DEVICE_TYPE_SENSOR = PLATFORM_SENSOR
DEVICE_TYPE_CLIMATE = PLATFORM_CLIMATE
DEVICE_TYPE_FAN = PLATFORM_FAN

# 设备类型 -> HA 平台集合。所有候选设备和实体平台均以此表为准。
# type=81 同时具备 climate 和 fan 能力，不能用单值映射表达。
DEVICE_PLATFORM_MAP = {
    device_type: profile.platforms for device_type, profile in DEVICE_PROFILES.items()
}

# 兼容旧代码和外部引用；新代码应使用 DEVICE_PLATFORM_MAP。
_PLATFORM_PRIORITY = (
    DEVICE_TYPE_LIGHT,
    DEVICE_TYPE_COVER,
    DEVICE_TYPE_CLIMATE,
    DEVICE_TYPE_FAN,
    DEVICE_TYPE_SENSOR,
    "binary_sensor",
)
DEVICE_TYPE_MAP = {
    device_type: next(platform for platform in _PLATFORM_PRIORITY if platform in platforms)
    for device_type, platforms in DEVICE_PLATFORM_MAP.items()
}

# 不暴露为实体的隐藏设备类型（MixPad、戴妃网关、开关底座、红外遥控、摄像头、音乐主机、射频类）
# 注意：Wifi直连设备（如 type=107/522 Wifi 门锁等）不在本表过滤，
# 而是由 coordinator.py 和 config_flow.py通过设备 uid 是否匹配网关 uid 来动态剔除。
HIDDEN_TYPES = {114, 510, 511, 518, 150, 14, 128, 135, 136, 137, 143, 155, 115}

# ---- 支持的平台 ----
PLATFORMS = ["light", "cover", "climate", "fan", "sensor", "binary_sensor"]
