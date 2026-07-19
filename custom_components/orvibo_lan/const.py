"""ORVIBO LAN Control 常量定义。"""

import os
from datetime import timedelta

# ---- HA 配置键 ----
DOMAIN = "orvibo_lan"
MANUFACTURER = "ORVIBO"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_FAMILY_ID = "family_id"
CONF_SELECTED_DEVICE_IDS = "selected_device_ids"

# ---- 更新间隔 ----
UPDATE_INTERVAL = timedelta(seconds=30)      # 从云端轮询状态
GATEWAY_DISCOVER_INTERVAL = timedelta(minutes=5)  # UDP 发现网关

# ---- 设备类型映射 ----
DEVICE_TYPE_COVER = "cover"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_SENSOR = "sensor"
DEVICE_TYPE_CLIMATE = "climate"
DEVICE_TYPE_FAN = "fan"

# 设备类型 → HA 平台映射
DEVICE_TYPE_MAP = {
    1: DEVICE_TYPE_LIGHT,           # 简版灯
    34: DEVICE_TYPE_COVER,          # 窗帘
    35: DEVICE_TYPE_COVER,          # 卷帘
    36: DEVICE_TYPE_CLIMATE,        # 空调
    38: DEVICE_TYPE_LIGHT,          # 调光调色灯
    52: "clothes_horse",            # 晾衣架（后续通过 service 实现）
    81: DEVICE_TYPE_CLIMATE,        # 空调/风机盘管（同 type=36）
    102: DEVICE_TYPE_LIGHT,         # 灯
    501: DEVICE_TYPE_LIGHT,         # 单色灯
    502: DEVICE_TYPE_LIGHT,         # 可调光灯
    503: DEVICE_TYPE_LIGHT,         # 色温灯带
    516: DEVICE_TYPE_FAN,           # 新风系统
    0: DEVICE_TYPE_LIGHT,           # Zigbee 调光灯
    # ---- 传感器 ----
    22: DEVICE_TYPE_SENSOR,         # 温湿度传感器
    23: DEVICE_TYPE_SENSOR,         # 温湿度传感器
    25: DEVICE_TYPE_SENSOR,         # 可燃气体探测器
    26: DEVICE_TYPE_SENSOR,         # 人体传感器
    27: DEVICE_TYPE_SENSOR,         # 烟雾传感器
    46: DEVICE_TYPE_SENSOR,         # 门窗传感器
    54: DEVICE_TYPE_SENSOR,         # 水浸探测器
    56: DEVICE_TYPE_SENSOR,         # 紧急按钮
    300: DEVICE_TYPE_SENSOR,        # 门锁/温湿度传感器
    522: DEVICE_TYPE_SENSOR,        # 门锁 V5
    107: DEVICE_TYPE_SENSOR,        # 门锁 T1
}

# 不暴露为实体的隐藏设备类型（MixPad、开关底座、红外遥控、摄像头、音乐主机、射频类）
HIDDEN_TYPES = {114, 511, 518, 150, 14, 128, 135, 136, 137, 143, 155, 115}

# ---- 支持的平台 ----
PLATFORMS = ["light", "cover", "climate", "fan", "sensor", "binary_sensor"]
