#!/usr/bin/env python3
"""设备控制路由层：完整payload构建（LAN协议）。

参考 orvibohomebridge.packet.HomemateJsonData 的 ssl_control_* 方法，
去掉相对导入依赖，适配 LAN 协议差异：
    LAN: groupid (小写), source: "ZhiJia365"
    SSL: groupId (大写), 无 source
"""

import logging
from typing import Any

from .serial import next_serial

_LOGGER = logging.getLogger(__name__)

SOFTWARE_VER = "5.1.5.302"
CMD_HELLO = 1
CMD_LOGIN = 3
CMD_CONTROL = 15
CMD_HEARTBEAT = 32


def _serial() -> int:
    return next_serial()


def _uni_serial() -> int:
    return next_serial()


def _to_lan(payload: dict[str, Any]) -> dict[str, Any]:
    """将 SSL 格式 payload 转为 LAN 格式。"""
    # 保留 groupId（App 会带 "groupId": ""），不再删除
    # AC（type=36）通过网关控制，需要 groupId 字段
    if "source" not in payload:
        payload["source"] = "ZhiJia365"
    # 注意：不再暴力删除 groupid/qualityOfService/defaultResponse/propertyResponse
    # 智家365 App 实际都会传这些字段。groupid 对 Zapier/Zigbee 设备有副作用，
    # 但 AC（type=36）不走 Zigbee，留着不影响。
    return payload


# ==================== 通用 base payload ====================


def _base(device_id: str, uid: str, username: str = "") -> dict:
    """所有控制命令共用的基础字段。"""
    return {
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "delayTime": 0,
        "cmd": CMD_CONTROL,
        "serial": _serial(),
        "clientType": 1,
        "uniSerial": _uni_serial(),
        "serverRecord": False,
        "ver": SOFTWARE_VER,
        "debugInfo": "Android_ZhiJia365_34_5.1.5.302",
    }


# ==================== 灯控制 ====================


def light_on(device_id: str, uid: str, device_type: int, username: str = "") -> dict:
    """开灯。"""
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type in {36, 501, 502, 503, 135, 136, 137, 143, 2, 554}:
        # set property 格式（空调保留 value2~value4）
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "order": "set property",
            "value1": 0,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"onoff": {"status": "on"}},
        }
    else:
        # order=on + value1=0
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "order": "on",
            "value1": 0,
            "value2": 255,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def light_off(device_id: str, uid: str, device_type: int, username: str = "") -> dict:
    """关灯。"""
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type in {36, 501, 502, 503, 135, 136, 137, 143, 2, 554}:
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "order": "set property",
            "value1": 0,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"onoff": {"status": "off"}},
        }
    else:
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "order": "off",
            "value1": 1,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def power_only_light(device_id: str, uid: str, state: bool, username: str = "") -> dict:
    """Control captured type-1/type-102 subtype-1 relay endpoints."""
    payload = _base(device_id, uid, username)
    payload.update(
        {
            "groupId": "",
            "order": "on" if state else "off",
            "value1": 0 if state else 1,
            "value2": 0,
            "value3": 0,
            "value4": 0,
        }
    )
    return _to_lan(payload)


def light_brightness(
    device_id: str, uid: str, device_type: int, brightness: int, username: str = ""
) -> dict:
    """设置亮度 0-255。"""
    bri = max(0, min(int(brightness), 255))
    serial = _serial()
    uniSerial = _uni_serial()
    if device_type in (502, 503):
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "set property",
            "value1": 0,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"brightness": {"percent": max(1, bri * 100 // 255)}},
        }
    elif device_type == 38:
        # 调光调色灯用 move to level（ZCL 标准调光）
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "order": "move to level",
            "value1": 0,
            "value2": bri,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    else:
        # type=102 等用 order=on + value2=亮度
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "on",
            "value1": 0,
            "value2": bri,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def light_colortemp(
    device_id: str,
    uid: str,
    device_type: int,
    kelvin: int,
    brightness: int = 255,
    username: str = "",
) -> dict:
    """设置色温 2700-6500K。"""
    ct = max(2700, min(int(kelvin), 6500))
    mired = 1000000 // ct
    bri = max(0, min(int(brightness), 255))
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type == 503:
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "set property",
            "value1": 0,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {"colorTemp": {"value": ct}},
        }
    else:
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "fast color temperature",
            "value1": 0,
            "value2": bri,
            "value3": mired,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


def light_on_off(
    device_id: str,
    uid: str,
    device_type: int,
    power: bool,
    brightness: int = 0,
    color_temp_k: int | None = None,
    username: str = "",
) -> dict:
    """一次性下发开关+亮度+色温（旧协议用 order=on/off + value2/value3）。"""
    bri = max(0, min(int(brightness), 255))
    serial = _serial()
    uniSerial = _uni_serial()

    if device_type == 503:
        # ThingModel 色温灯带：用 set property
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "set property",
            "value1": 0,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {
                "onoff": {"status": "on" if power else "off"},
                "brightness": {"percent": max(1, bri * 100 // 255)},
            },
        }
        if color_temp_k:
            ct = max(2700, min(int(color_temp_k), 6500))
            properties = payload.get("properties")
            if isinstance(properties, dict):
                properties["colorTemp"] = {"value": ct}
    elif device_type in (502, 102):
        # ThingModel 调光灯：用 set property
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "set property",
            "value1": 0,
            "value2": 0,
            "value3": 0,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "properties": {
                "onoff": {"status": "on" if power else "off"},
                "brightness": {"percent": max(1, bri * 100 // 255)},
            },
        }
    else:
        # 旧协议：order=on/off, value2=亮度, value3=色温(mired)
        ct_val = 0
        if color_temp_k:
            ct_val = 1000000 // max(2700, min(int(color_temp_k), 6500))
        payload = {
            "uid": uid,
            "userName": username,
            "deviceId": device_id,
            "groupId": "",
            "order": "on" if power else "off",
            "value1": 0 if power else 1,
            "value2": bri,
            "value3": ct_val,
            "value4": 0,
            "delayTime": 0,
            "cmd": CMD_CONTROL,
            "serial": serial,
            "clientType": 1,
            "uniSerial": uniSerial,
            "serverRecord": False,
            "ver": SOFTWARE_VER,
        }
    return _to_lan(payload)


# ==================== 开关控制 ====================


def switch_control(device_id: str, uid: str, state: bool, username: str = "") -> dict:
    """开关控制（set property 格式，type=501/135/136 等）。"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "groupId": "",
        "order": "set property",
        "value1": 0,
        "value2": 0,
        "value3": 0,
        "value4": 0,
        "delayTime": 0,
        "cmd": CMD_CONTROL,
        "serial": serial,
        "clientType": 1,
        "uniSerial": uniSerial,
        "serverRecord": False,
        "ver": SOFTWARE_VER,
        "properties": {"onoff": {"status": "on" if state else "off"}},
    }
    return _to_lan(payload)


# ==================== 窗帘控制 ====================


def curtain_position(
    device_id: str,
    uid: str,
    position: int | str,
    username: str = "",
) -> dict:
    """控制窗帘位置。position: 0-100 或 'stop'。"""
    serial = _serial()
    uniSerial = _uni_serial()

    if isinstance(position, str) and position == "stop":
        order, value1 = "stop", 0
    else:
        pos = max(0, min(int(position), 100))
        order = "close" if pos == 0 else "open"
        value1 = pos

    payload = {
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "groupId": "",
        "order": order,
        "value1": value1 if order != "stop" else 0,
        "value2": 0,
        "value3": 0,
        "value4": 0,
        "delayTime": 0,
        "cmd": CMD_CONTROL,
        "serial": serial,
        "clientType": 1,
        "uniSerial": uniSerial,
        "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


# ==================== 新风系统 ====================


def ventilation_control(device_id: str, uid: str, value1: int, username: str = "") -> dict:
    """新风控制。value1: 0=慢, 50=停, 100=快。"""
    serial = _serial()
    uniSerial = _uni_serial()
    payload = {
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "groupId": "",
        "order": "set property",
        "value1": value1,
        "value2": 0,
        "value3": 0,
        "value4": 0,
        "delayTime": 0,
        "cmd": CMD_CONTROL,
        "serial": serial,
        "clientType": 1,
        "uniSerial": uniSerial,
        "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return _to_lan(payload)


def fan_on(device_id: str, uid: str, device_type: int, username: str = "") -> dict:
    """Turn on a verified ventilation profile at its fast preset."""
    return ventilation_control(device_id, uid, 100, username)


def fan_off(device_id: str, uid: str, device_type: int, username: str = "") -> dict:
    """Stop a ventilation profile."""
    return ventilation_control(device_id, uid, 50, username)


def fan_set_speed(
    device_id: str, uid: str, device_type: int, percentage: int, username: str = ""
) -> dict:
    """Map HA percentage to the protocol's slow/stop/fast presets."""
    requested = max(0, min(int(percentage), 100))
    if requested == 0:
        value1 = 50
    elif requested <= 50:
        value1 = 0
    else:
        value1 = 100
    return ventilation_control(device_id, uid, value1, username)


# ==================== 空调控制 (type=36) ====================


def _ac_base(device_id: str, uid: str, username: str = "") -> dict:
    """空调控制命令基础字段，对齐智家365 App 的格式。"""
    return {
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "groupId": "",
        "delayTime": 0,
        "qualityOfService": 1,
        "defaultResponse": 1,
        "propertyResponse": 0,
        "cmd": CMD_CONTROL,
        "serial": _serial(),
        "clientType": 1,
        "uniSerial": _uni_serial(),
        "serverRecord": False,
        "ver": SOFTWARE_VER,
        "debugInfo": "Android_ZhiJia365_34_5.1.5.302",
    }


def ac_off(device_id: str, uid: str, username: str = "") -> dict:
    """关空调。"""
    payload = _ac_base(device_id, uid, username)
    payload.update(
        {
            "order": "off",
            "value1": 1,
            "value2": 0,
            "value3": 0,
            "value4": 0,
        }
    )
    return _to_lan(payload)


def ac_on_with_mode(
    device_id: str,
    uid: str,
    mode: int,
    username: str = "",
    current_state: dict[str, Any] | None = None,
) -> dict:
    """开空调 + 切模式。App 用 order='on' 开机，用 order='mode setting' 切换模式。

    从关机状态开机时用 order='on'（App 实测）。
    运行中切模式用 order='mode setting'（已有逻辑保留）。
    传入 current_state 可继承当前温度和风速。
    """
    temp = 2500  # 默认 25°C
    fan = 1  # 默认低风
    if current_state:
        v3 = current_state.get("value3", 0)
        if v3 and 1 <= int(v3) <= 3:
            fan = int(v3)
        v4 = current_state.get("value4", 0)
        if v4:
            hi = int(v4) >> 16
            if hi > 0:
                temp = hi

    payload = _ac_base(device_id, uid, username)
    payload.update(
        {
            "order": "on",  # App 用 "on" 开机，不是 "mode setting"
            "value1": 0,
            "value2": mode,
            "value3": fan,
            "value4": temp << 16,
        }
    )
    return _to_lan(payload)


def ac_power(device_id: str, uid: str, on: bool, username: str = "") -> dict:
    """空调电源。on=True → mode setting, on=False → off"""
    if on:
        return ac_on_with_mode(device_id, uid, 3, username=username)
    else:
        return ac_off(device_id, uid, username=username)


def ac_mode(device_id: str, uid: str, mode: int, username: str = "") -> dict:
    """空调模式。"""
    payload = _ac_base(device_id, uid, username)
    payload.update(
        {
            "order": "mode setting",
            "value1": 0,
            "value2": mode,
            "value3": 1,
            "value4": 2500 << 16,
        }
    )
    return _to_lan(payload)


def ac_set_temp(
    device_id: str,
    uid: str,
    temp: int,
    username: str = "",
    current_state: dict[str, Any] | None = None,
) -> dict:
    """空调温度。App 带 value2=当前模式, value3=当前风速。"""
    mode = 3  # 默认制冷
    fan = 1  # 默认低风
    if current_state:
        v2 = current_state.get("value2", 0)
        if v2:
            mode = int(v2)
        v3 = current_state.get("value3", 0)
        if v3 and 1 <= int(v3) <= 3:
            fan = int(v3)

    payload = _ac_base(device_id, uid, username)
    payload.update(
        {
            "order": "temperature setting",
            "value1": 0,
            "value2": mode,
            "value3": fan,
            "value4": (temp * 100) << 16,
        }
    )
    return _to_lan(payload)


def ac_wind(
    device_id: str,
    uid: str,
    speed: int,
    username: str = "",
    current_state: dict[str, Any] | None = None,
) -> dict:
    """空调风速。App 带 value2=当前模式, value4=当前温度。"""
    mode = 3  # 默认制冷
    temp = 2500  # 默认25°C
    if current_state:
        v2 = current_state.get("value2", 0)
        if v2:
            mode = int(v2)
        v4 = current_state.get("value4", 0)
        if v4:
            hi = int(v4) >> 16
            if hi > 0:
                temp = hi

    payload = _ac_base(device_id, uid, username)
    payload.update(
        {
            "order": "wind setting",
            "value1": 0,
            "value2": mode,
            "value3": speed,
            "value4": temp << 16,
        }
    )
    return _to_lan(payload)


# ==================== 窗帘控制补充 ====================


def cover_open(device_id: str, uid: str, username: str = "") -> dict:
    return curtain_control(device_id, uid, "open", username)


def cover_close(device_id: str, uid: str, username: str = "") -> dict:
    return curtain_control(device_id, uid, "close", username)


def cover_stop(device_id: str, uid: str, username: str = "") -> dict:
    return curtain_control(device_id, uid, "stop", username)


def cover_position(
    device_id: str,
    uid: str,
    position: int,
    username: str = "",
) -> dict:
    return curtain_control(device_id, uid, max(0, min(int(position), 100)), username)


def _curtain_property_base(
    device_id: str,
    uid: str,
    username: str = "",
) -> dict:
    serial = _serial()
    uniSerial = _uni_serial()
    return {
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "groupId": "",
        "order": "set property",
        "value1": 0,
        "value2": 0,
        "value3": 0,
        "value4": 0,
        "delayTime": 0,
        "cmd": CMD_CONTROL,
        "serial": serial,
        "clientType": 1,
        "uniSerial": uniSerial,
        "serverRecord": False,
        "ver": SOFTWARE_VER,
        "properties": {},
    }


def cover_curtain_angle_open(
    device_id: str,
    uid: str,
    angle_deg: int,
    username: str = "",
) -> dict:
    """梦幻帘(506)打开。set property curtain percent=100，保留叶片角度。"""
    payload = _curtain_property_base(device_id, uid, username)
    payload["properties"] = {
        "curtain": {"percent": 100, "angle": max(0, min(int(angle_deg), 180))}
    }
    return _to_lan(payload)


def cover_curtain_angle_close(
    device_id: str,
    uid: str,
    angle_deg: int,
    username: str = "",
) -> dict:
    """梦幻帘(506)关闭。set property curtain percent=0，保留叶片角度。"""
    payload = _curtain_property_base(device_id, uid, username)
    payload["properties"] = {
        "curtain": {"percent": 0, "angle": max(0, min(int(angle_deg), 180))}
    }
    return _to_lan(payload)


def cover_curtain_angle_stop(
    device_id: str,
    uid: str,
    username: str = "",
) -> dict:
    """梦幻帘(506)停止。set property curtain action=stop。"""
    payload = _curtain_property_base(device_id, uid, username)
    payload["properties"] = {"curtain": {"action": "stop"}}
    return _to_lan(payload)


def cover_curtain_angle_position(
    device_id: str,
    uid: str,
    position: int,
    angle_deg: int,
    username: str = "",
) -> dict:
    """梦幻帘(506)位置控制。set property curtain percent=位置, angle=角度。"""
    payload = _curtain_property_base(device_id, uid, username)
    payload["properties"] = {
        "curtain": {
            "percent": max(0, min(int(position), 100)),
            "angle": max(0, min(int(angle_deg), 180)),
        }
    }
    return _to_lan(payload)


def cover_curtain_angle_tilt(
    device_id: str,
    uid: str,
    angle_deg: int,
    position: int,
    username: str = "",
) -> dict:
    """梦幻帘(506)叶片角度控制。set property curtain angle=度数, percent=保持。"""
    payload = _curtain_property_base(device_id, uid, username)
    payload["properties"] = {
        "curtain": {
            "angle": max(0, min(int(angle_deg), 180)),
            "percent": max(0, min(int(position), 100)),
        }
    }
    return _to_lan(payload)


def curtain_control(
    device_id: str,
    uid: str,
    cmd: str | int,
    username: str = "",
) -> dict:
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
        "uid": uid,
        "userName": username,
        "deviceId": device_id,
        "order": order,
        "value1": value1,
        "value2": 0,
        "value3": 0,
        "value4": 0,
        "delayTime": 0,
        "cmd": CMD_CONTROL,
        "serial": serial,
        "clientType": 1,
        "uniSerial": uniSerial,
        "serverRecord": False,
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
        "serial": serial,
        "clientType": 1,
        "uniSerial": uniSerial,
        "serverRecord": False,
        "ver": SOFTWARE_VER,
    }
    return payload
