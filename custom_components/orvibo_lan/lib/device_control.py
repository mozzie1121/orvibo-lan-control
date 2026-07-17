#!/usr/bin/env python3
"""设备控制路由层：完整payload构建（LAN协议）。

参考 orvibohomebridge.packet.HomemateJsonData 的 ssl_control_* 方法，
去掉相对导入依赖，适配 LAN 协议差异：
  LAN: groupid (小写), source: "ZhiJia365"
  SSL: groupId (大写), 无 source
"""

import logging
import time
from typing import Optional

_LOGGER = logging.getLogger(__name__)

SOFTWARE_VER = "5.1.3.309"
CMD_HELLO = 1
CMD_LOGIN = 3
CMD_CONTROL = 15
CMD_HEARTBEAT = 32
CMD_CLOTHES_HORSE_CONTROL = 98
CMD_CLOTHES_HORSE_QUERY = 100


def _serial():
    return int(time.time() * 1000000) % 1000000


def _uni_serial():
    return int(time.time() * 1000) % 1000000


def _to_lan(payload: dict) -> dict:
    """将 SSL 格式 payload 转为 LAN 格式。"""
    if "groupId" in payload:
        payload.pop("groupId")
    if "groupid" in payload:
        payload.pop("groupid")
    if "source" not in payload:
        payload["source"] = "ZhiJia365"
    # LAN 不用的字段
    payload.pop("qualityOfService", None)
    payload.pop("defaultResponse", None)
    payload.pop("propertyResponse", None)
    return payload


# ==================== 灯控制 ====================

def light_on(device_id: str, uid: str, device_type: int,
             username: str = "") -> dict:
    """开灯。"""
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type in {36, 501, 502, 503, 135, 136, 137, 143, 2, 554}:
        # set property 格式（空调保留 value2~value4）
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id,
            "order": "set property",
            "value1": 0, "value2": 0, "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"onoff": {"status": "on"}},
        }
    else:
        # order=on + value1=0
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id,
            "order": "on", "value1": 0, "value2": 255,
            "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def light_off(device_id: str, uid: str, device_type: int,
              username: str = "") -> dict:
    """关灯。"""
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type in {36, 501, 502, 503, 135, 136, 137, 143, 2, 554}:
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id,
            "order": "set property",
            "value1": 0, "value2": 0, "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"onoff": {"status": "off"}},
        }
    else:
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id,
            "order": "off", "value1": 1, "value2": 0,
            "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def light_brightness(device_id: str, uid: str, device_type: int,
                     brightness: int, username: str = "") -> dict:
    """设置亮度 0-255。"""
    bri = max(0, min(int(brightness), 255))
    serial = _serial()
    uniSerial = _uni_serial()
    if device_type == 503:
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id, "groupId": "",
            "order": "set property",
            "value1": 0, "value2": 0, "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"brightness": {"percent": max(1, bri * 100 // 255)}},
        }
    elif device_type == 502:
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id, "groupId": "",
            "order": "set property",
            "value1": 0, "value2": 0, "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"brightness": {"percent": max(1, bri * 100 // 255)}},
        }
    elif device_type == 38:
        # 调光调色灯用 move to level（ZCL 标准调光）
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id,
            "order": "move to level",
            "value1": 0, "value2": bri, "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    else:
        # type=102 等用 order=on + value2=亮度
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id, "groupId": "",
            "order": "on",
            "value1": 0, "value2": bri,
            "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def light_colortemp(device_id: str, uid: str, device_type: int,
                    kelvin: int, brightness: int = 255,
                    username: str = "") -> dict:
    """设置色温 2700-6500K。"""
    ct = max(2700, min(int(kelvin), 6500))
    mired = 1000000 // ct
    bri = max(0, min(int(brightness), 255))
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type == 503:
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id, "groupId": "",
            "order": "set property",
            "value1": 0, "value2": 0, "value3": 0, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"colorTemp": {"value": ct}},
        }
    else:
        payload = {
            "uid": uid, "userName": username,
            "deviceId": device_id, "groupId": "",
            "order": "fast color temperature",
            "value1": 0, "value2": bri, "value3": mired, "value4": 0,
            "delayTime": 0, "cmd": CMD_CONTROL,
            "serial": serial, "clientType": 1,
            "uniSerial": uniSerial, "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


# ==================== 开关控制 ====================

def switch_control(device_id: str, uid: str, state: bool,
                   username: str = "") -> dict:
    """开关控制（set property 格式，type=501/135/136 等）。"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id, "groupId": "",
        "order": "set property",
        "value1": 0, "value2": 0, "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
        "properties": {"onoff": {"status": "on" if state else "off"}},
    }
    return _to_lan(payload)


# ==================== 窗帘控制 ====================

def curtain_position(device_id: str, uid: str, position,
                     username: str = "") -> dict:
    """控制窗帘位置。position: 0-100 或 'stop'。"""
    serial = _serial()
    uniSerial = _uni_serial()

    if isinstance(position, str) and position == "stop":
        order, value1 = "stop", 0
    else:
        pos = max(0, min(int(position), 100))
        order = "close" if pos == 0 else "open"
        value1 = pos

    if order == "close":
        order2, value1_2 = "off", 1
    else:
        order2, value1_2 = "on", value1

    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id, "groupId": "",
        "order": order, "value1": value1 if order != "stop" else 0,
        "value2": 0, "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 晾衣架 ====================

def clothes_horse_control(device_id: str, uid: str,
                          ctrl_field: str, ctrl_value: str,
                          username: str = "") -> dict:
    # 晾衣架控制(cmd=98)
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        ctrl_field: ctrl_value,
        "cmd": CMD_CLOTHES_HORSE_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 新风系统 ====================

def ventilation_control(device_id: str, uid: str, value1: int,
                        username: str = "") -> dict:
    """新风控制。value1: 0=慢, 50=停, 100=快。"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id, "groupId": "",
        "order": "set property",
        "value1": value1, "value2": 0, "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 空调 ====================

def ac_control(device_id: str, uid: str,
               value1: int = None, value2: int = None,
               value3: int = None, value4: int = None,
               username: str = "") -> dict:
    """空调控制（set property 格式）。"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id, "groupId": "",
        "order": "set property",
        "value1": value1 or 0, "value2": value2 or 0,
        "value3": value3 or 0, "value4": value4 or 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 窗帘控制补充 ====================

def cover_open(device_id: str, uid: str, username: str = "") -> dict:
    return curtain_control(device_id, uid, "open", username)


def cover_close(device_id: str, uid: str, username: str = "") -> dict:
    return curtain_control(device_id, uid, "close", username)


def cover_stop(device_id: str, uid: str, username: str = "") -> dict:
    return curtain_control(device_id, uid, "stop", username)


def cover_position(device_id: str, uid: str, position,
                   username: str = "") -> dict:
    return curtain_control(device_id, uid, max(0, min(int(position), 100)),
                           username)


def curtain_control(device_id: str, uid: str, cmd, username: str = "") -> dict:
    serial = _serial()
    uniSerial = _uni_serial()

    if cmd == "open":
        order, value1 = "on", 100
    elif cmd == "close":
        order, value1 = "off", 0
    elif cmd == "stop":
        order, value1 = "stop", 0
    else:
        pos = max(0, min(int(cmd), 100))
        order = "on" if pos >= 50 else "off"
        value1 = pos

    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        "order": order, "value1": value1,
        "value2": 0, "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 空调控制 (type=36, 实测通过的格式) ====================
# 实测结果:
#   关:      order="off"  value1=1              (通用关格式)
#   开+模式:  order="mode setting"  value1=0  value2=模式码
#   切模式:  order="mode setting"  value2=3/4/7/2
#   设温度:  order="temperature setting"  value4=(temp*100)<<16
#   设风速:  order="wind setting"  value3=1/2/3
# ❌ set property + properties.onoff — 无效
# ❌ ac control + subOrder — 无效

def ac_off(device_id: str, uid: str, username: str = "") -> dict:
    """关空调。实测: order='off', value1=1"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        "order": "off", "value1": 1, "value2": 0,
        "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


def ac_on_with_mode(device_id: str, uid: str, mode: int,
                    username: str = "") -> dict:
    """开空调 + 切模式。实测: order='mode setting', value1=0, value2=mode"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        "order": "mode setting",
        "value1": 0, "value2": mode,
        "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# 保留原有的 ac_* 函数但标记为 legacy（背后用实测通过的格式）
def ac_power(device_id: str, uid: str, on: bool,
             username: str = "") -> dict:
    """空调电源。on=True → mode setting+v1=0(开), on=False → off+v1=1(关)"""
    if on:
        return ac_on_with_mode(device_id, uid, 3, username=username)
    else:
        return ac_off(device_id, uid, username=username)


def ac_mode(device_id: str, uid: str, mode: int,
            username: str = "") -> dict:
    """空调模式。实测: order='mode setting', value2=模式码"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        "order": "mode setting",
        "value1": 0, "value2": mode,
        "value3": 0, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


def ac_set_temp(device_id: str, uid: str, temp: int,
                username: str = "") -> dict:
    """空调温度。实测: order='temperature setting', value4=(temp*100)<<16"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        "order": "temperature setting",
        "value1": 0, "value2": 0, "value3": 0,
        "value4": (temp * 100) << 16,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


def ac_wind(device_id: str, uid: str, speed: int,
            username: str = "") -> dict:
    """空调风速。实测: order='wind setting', value3=1/2/3"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid, "userName": username,
        "deviceId": device_id,
        "order": "wind setting",
        "value1": 0, "value2": 0,
        "value3": speed, "value4": 0,
        "delayTime": 0, "cmd": CMD_CONTROL,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 心跳包 ====================

def heartbeat() -> dict:
    """构建心跳包(cmd=32)。"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "cmd": CMD_HEARTBEAT,
        "serial": serial, "clientType": 1,
        "uniSerial": uniSerial, "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return payload


# ==================== 设备类型信息 ====================

DEVICE_TYPE_NAMES = {
    1: "简版灯", 34: "窗帘", 36: "空调",
    38: "调光调色灯", 52: "晾衣架", 81: "AirMaster",
    102: "灯", 114: "MixPad主机", 501: "单色灯",
    502: "可调光灯", 503: "色温灯带", 516: "新风",
    2: "开关", 554: "开关", 511: "四路底壳", 518: "扩展开关",
    0: "Zigbee调光灯",
    25: "燃气传感器", 26: "人体传感器", 27: "烟雾传感器",
    46: "门窗传感器", 54: "水浸传感器", 56: "紧急按钮",
    135: "智能开关", 136: "智能开关", 137: "智能开关", 143: "智能开关",
    150: "智能遥控", 300: "温湿度传感器",
}

CONTROLLABLE_TYPES = {1, 34, 36, 38, 52, 81, 102,
                      501, 502, 503, 516, 0, 2, 554,
                      135, 136, 137, 143, 150}


def get_device_type_name(dt: int) -> str:
    return DEVICE_TYPE_NAMES.get(dt, f"未知({dt})")


def is_set_property(dt: int) -> bool:
    return dt in {501, 135, 136, 137, 143, 2, 554, 502, 516, 36}
