#!/usr/bin/env python3
"""
Orvibo 局域网控制 CLI（纯离线控制）

原理：
  - 通过 HTTPS 云端 API 获取设备列表 + 网关 IP（不依赖 mDNS/UDP 发现）
  - 通过局域网 TCP 8088 直接控制设备（不走云端）
  - 自动找对所属网关进行控制

用法：
  python3 main.py list                    # 列出设备（含网关IP）
  python3 main.py list --online           # 仅列出在线设备
  python3 main.py on   <关键词>             # 开灯/开开关
  python3 main.py off  <关键词>             # 关灯/关开关
  python3 main.py bright <关键词> <0-255>  # 调亮度
  python3 main.py temp  <关键词> <2700-6500>  # 调色温(K)
  python3 main.py curtain <关键词> <0-100> # 窗帘位置
  python3 main.py curtain <关键词> stop    # 窗帘停止
  python3 main.py discover                # UDP发现网关
  python3 main.py connect <网关IP> [用户] [密码]  # 测试连接指定网关

首次使用需设置账号：
  export ORVIBO_PHONE="手机号"
  export ORVIBO_PASSWORD="密码"
  或创建当前目录下的 .env 文件

作者参考 orvibohomebridge 在线控制部分的登录、设备解析、控制命令格式实现。
"""
# 确保当前目录在模块搜索路径中（支持直接 python main.py 运行）
import sys
import os
import asyncio
import logging
import json
from typing import Optional
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# 尝试加载 .env（优先当前目录，再回退到 /root/lan_control）
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if not os.path.exists(_env_path):
    _env_path = "/root/lan_control/.env"
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from packet import (
    DEFAULT_KEY, PK_TYPE, ID_UNSET,
    build_packet, parse_packet,
)
from https_client import HttpsClient
from lan_controller import LanConnection
from device_control import (
    light_on, light_off, light_brightness, light_colortemp,
    curtain_position, switch_control, clothes_horse_control,
    ventilation_control, get_device_type_name,
    is_set_property, CONTROLLABLE_TYPES,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger("orvibo")


def get_credentials():
    phone = os.environ.get("ORVIBO_PHONE") or os.environ.get("PHONE")
    password = os.environ.get("ORVIBO_PASSWORD") or os.environ.get("PASSWORD")
    if not phone or not password:
        print("❌ 未设置账号密码。请设置环境变量:")
        print("   set ORVIBO_PHONE=手机号")
        print("   set ORVIBO_PASSWORD=密码")
        print("   或创建当前目录下的 .env 文件")
        sys.exit(1)
    return phone, password


# ==================== 命令实现 ====================

async def cmd_list(online_only: bool = False):
    phone, password = get_credentials()
    client = HttpsClient(phone, password)
    devices, statuses, gateways, gateway_ips, get_gw = await client.fetch_devices()

    # 建立 MixPad 名称映射
    mixpad_names = {}
    for d in devices:
        if d.get("deviceType") == 114:
            mixpad_names[d.get("deviceId", "")] = d.get("deviceName", "?")
    for g in gateways:
        gid = g.get("gatewayId") or g.get("deviceId", "")
        mixpad_names[gid] = g.get("homeName", "") or g.get("model", gid[:12])

    print(f"\n📋 设备列表 ({len(devices)} 个) | 在线网关: {len([v for v in gateway_ips.values() if v])} 个\n")
    print(f"{'设备名':24s} {'类型':6s} {'状态':8s} {'亮度':5s} {'在线':5s} {'所属网关/IP'}")
    print("-" * 85)

    count = 0
    for d in sorted(devices, key=lambda x: x.get("deviceName", "")):
        did = d["deviceId"]
        st = statuses.get(did, {})
        name = d.get("deviceName", "?")
        dt_raw = d.get("deviceType", 0)
        dt = int(dt_raw) if isinstance(dt_raw, str) else dt_raw
        type_name = get_device_type_name(dt)

        v1 = st.get("value1", -1)
        v2 = st.get("value2", -1)
        online = st.get("online", 0)

        if online_only and online != 1:
            continue

        # 判断状态
        if dt in {34}:
            # 窗帘用 position
            pos = st.get("position", st.get("value1", 0))
            state = f"{pos}%"
        elif dt in {36}:
            # 空调
            ac_state = "开" if v1 == 0 else "关"
            mode_map = {2: "除湿", 3: "制冷", 4: "制热", 7: "送风"}
            fan_map = {1: "低", 2: "中", 3: "高"}
            v2 = st.get("value2", -1)
            v3 = st.get("value3", -1)
            ac_mode = mode_map.get(v2, f"?{v2}")
            ac_fan = fan_map.get(v3, f"?{v3}")
            state = f"{ac_state}"
            bri_str = f"{ac_mode}/{ac_fan}"
        elif dt in {501, 502, 135, 136, 137, 143, 2, 554, 503}:
            # 501/502/503 等用 properties 格式
            props = st.get("properties", {}) or {}
            onoff = props.get("onoff", {})
            if isinstance(onoff, dict) and onoff.get("status") == "on":
                state = "开"
            elif isinstance(onoff, dict) and onoff.get("status") == "off":
                state = "关"
            elif isinstance(props.get("onoff_status"), str):
                state = "开" if props["onoff_status"] == "on" else "关"
            elif v1 == 0:
                state = "开"
            elif v1 == 1:
                state = "关"
            else:
                state = "?"
            # 亮度
            bri_obj = props.get("brightness", {})
            if isinstance(bri_obj, dict):
                bri_pct = bri_obj.get("percent")
                if bri_pct is not None:
                    bri_str = str(bri_pct)
        elif v1 == 0:
            state = "开"
        elif v1 == 1:
            state = "关"
        elif v1 == -1:
            state = "?"
        else:
            state = f"v1={v1}"
        bri_str = str(v2) if v2 != -1 else "-"

        online_str = "✅" if online == 1 else "❌"

        # 找所属网关（通过设备 uid 匹配网关 IP）
        dev_uid = d.get("uid", "")
        if dev_uid in gateway_ips and gateway_ips[dev_uid]:
            gw_display = f"{gateway_ips[dev_uid]}"
        else:
            gw_display = "直连"

        print(f"{name[:24]:24s} {dt:>4d} {state:8s} {bri_str:5s} {online_str:5s} {gw_display}")
        count += 1

    print(f"\n共 {count} 个设备")
    print(f"可用命令: on/off/bright/temp/curtain + 设备名关键词")


async def cmd_on_off(action: str, keyword: str):
    phone, password = get_credentials()
    client = HttpsClient(phone, password)
    devices, statuses, _, gateway_ips, get_gw = await client.fetch_devices()

    matched = _find_devices(devices, keyword)
    if not matched:
        print(f"❌ 未找到匹配 \"{keyword}\" 的设备")
        return

    for d in matched:
        dt_raw = d.get("deviceType", 0)
        dt = int(dt_raw) if isinstance(dt_raw, str) else dt_raw
        name = d.get("deviceName", "?")
        did = d["deviceId"]
        uid = d.get("uid", "")

        print(f"\n🔧 [{name}] type={dt}")

        try:
            gw_ip = _get_gateway_ip(d, gateway_ips, get_gw)
            conn = await _connect(did, uid, gw_ip, phone, password)
            if not conn:
                continue

            if action == "on":
                payload = light_on(did, uid, dt, phone)
            else:
                payload = light_off(did, uid, dt, phone)

            if dt == 36:
                # 空调不回复确认包，直接发完算成功
                await conn.send_control(payload)
                print(f"  ✅ {'开' if action == 'on' else '关'}成功")
            else:
                result = await conn.send_control(payload)
                if result and result.get("status") == 0:
                    print(f"  ✅ {'开' if action == 'on' else '关'}成功")
                elif result:
                    print(f"  ⚠️ 回复: status={result.get('status')}")
                else:
                    print(f"  ❌ 无回复")
            await conn.close()
        except Exception as e:
            print(f"  ❌ 错误: {e}")


async def cmd_bright(keyword: str, brightness: int):
    phone, password = get_credentials()
    client = HttpsClient(phone, password)
    devices, _, _, gateway_ips, get_gw = await client.fetch_devices()

    matched = _find_devices(devices, keyword)
    if not matched:
        print(f"❌ 未找到匹配 \"{keyword}\" 的设备")
        return

    for d in matched:
        dt_raw = d.get("deviceType", 0)
        dt = int(dt_raw) if isinstance(dt_raw, str) else dt_raw
        name = d.get("deviceName", "?")
        did = d["deviceId"]
        uid = d.get("uid", "")

        print(f"\n🔧 [{name}] type={dt} 亮度={brightness}")
        try:
            gw_ip = _get_gateway_ip(d, gateway_ips, get_gw)
            conn = await _connect(did, uid, gw_ip, phone, password)
            if not conn:
                continue

            payload = light_brightness(did, uid, dt, brightness, phone)
            result = await conn.send_control(payload)
            if result and result.get("status") == 0:
                print(f"  ✅ 亮度设置成功")
            else:
                print(f"  ⚠️ 回复: {result}")
            await conn.close()
        except Exception as e:
            print(f"  ❌ 错误: {e}")


async def cmd_temp(keyword: str, kelvin: int):
    phone, password = get_credentials()
    client = HttpsClient(phone, password)
    devices, _, _, gateway_ips, get_gw = await client.fetch_devices()

    matched = _find_devices(devices, keyword)
    if not matched:
        print(f"❌ 未找到匹配 \"{keyword}\" 的设备")
        return

    for d in matched:
        dt_raw = d.get("deviceType", 0)
        dt = int(dt_raw) if isinstance(dt_raw, str) else dt_raw
        name = d.get("deviceName", "?")
        did = d["deviceId"]
        uid = d.get("uid", "")

        print(f"\n🔧 [{name}] type={dt} 色温={kelvin}K")
        try:
            gw_ip = _get_gateway_ip(d, gateway_ips, get_gw)
            conn = await _connect(did, uid, gw_ip, phone, password)
            if not conn:
                continue

            payload = light_colortemp(did, uid, dt, kelvin, username=phone)
            result = await conn.send_control(payload)
            if result and result.get("status") == 0:
                print(f"  ✅ 色温设置成功")
            else:
                print(f"  ⚠️ 回复: {result}")
            await conn.close()
        except Exception as e:
            print(f"  ❌ 错误: {e}")


async def cmd_curtain(keyword: str, position):
    phone, password = get_credentials()
    client = HttpsClient(phone, password)
    devices, _, _, gateway_ips, get_gw = await client.fetch_devices()

    matched = _find_devices(devices, keyword)
    if not matched:
        print(f"❌ 未找到匹配 \"{keyword}\" 的设备")
        return

    for d in matched:
        dt_raw = d.get("deviceType", 0)
        dt = int(dt_raw) if isinstance(dt_raw, str) else dt_raw
        name = d.get("deviceName", "?")
        did = d["deviceId"]
        uid = d.get("uid", "")

        print(f"\n🔧 [{name}] type={dt} 窗帘={position}")
        try:
            gw_ip = _get_gateway_ip(d, gateway_ips, get_gw)
            conn = await _connect(did, uid, gw_ip, phone, password)
            if not conn:
                continue

            payload = curtain_position(did, uid, position, phone)
            result = await conn.send_control(payload)
            if result and result.get("status") == 0:
                print(f"  ✅ 窗帘操作成功")
            else:
                print(f"  ⚠️ 回复: {result}")
            await conn.close()
        except Exception as e:
            print(f"  ❌ 错误: {e}")


# ==================== 工具函数 ====================

def _find_devices(devices: list, keyword: str) -> list:
    kw = keyword.lower()
    matched = []
    for d in devices:
        name = d.get("deviceName", "").lower()
        did = d.get("deviceId", "").lower()
        if kw in name or kw in did:
            matched.append(d)
    return matched


def _get_gateway_ip(device, gateway_ips, get_gw) -> Optional[str]:
    dev_uid = device.get("uid", "")
    gw_ip = gateway_ips.get(dev_uid)
    if not gw_ip:
        return "10.0.0.160"  # 兜底：云端没IP信息时用已知的PM3
    if ":" in gw_ip:
        gw_ip = gw_ip.split(":")[0]
    return gw_ip


async def _connect(did, uid, gw_ip, phone, password) -> Optional[LanConnection]:
    print(f"  📡 连接 {gw_ip}:8088...")
    conn = LanConnection(gw_ip)
    ok = await conn.connect_and_login(phone, password)
    if not ok:
        # 如果云端给的网关连不上，试兜底网关
        fallback = "10.0.0.160"
        if gw_ip != fallback:
            print(f"  ⚠️ {gw_ip} 连接失败，尝试兜底网关 {fallback}...")
            conn = LanConnection(fallback)
            ok = await conn.connect_and_login(phone, password)
    if not ok:
        print(f"  ❌ 连接/登录失败")
        return None
    return conn


# ==================== UDP 发现 ====================

async def cmd_discover():
    """UDP 广播发现局域网内的 Orvibo 网关。"""
    from cmd_discover import cmd_discover as _cmd_discover
    return await _cmd_discover()


# ==================== TCP 状态监听 ====================

async def cmd_listen():
    """TCP 连接网关，监听设备状态推送（cmd=42）。"""
    import signal
    from lan_listener import TcpStatusListener, status_to_text

    phone, password = get_credentials()

    # 从云端获取所有网关IP
    client = HttpsClient(phone, password)
    _, _, _, gateway_ips, _ = await client.fetch_devices()

    if not gateway_ips:
        print("❌ 未发现任何网关")
        return

    # 显示找到的网关
    print(f"\n📡 找到 {len(gateway_ips)} 个网关:")
    for uid, ip in gateway_ips.items():
        print(f"   {uid[:16]}... @ {ip}")

    # 选择第一个可用的
    gw_ip = list(gateway_ips.values())[0]
    print(f"\n🔌 连接 {gw_ip}:8088...")
    print("   Ctrl+C 退出\n")

    try:
        listener = await TcpStatusListener.create(gw_ip, phone, password)
    except ConnectionError as e:
        print(f"❌ {e}")
        return

    def on_status(payload):
        line = status_to_text(payload)
        print(f"  {line}")

    # 注册信号优雅退出
    stop_future = asyncio.get_event_loop().create_future()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: stop_future.set_result(None))
        except (NotImplementedError, ValueError):
            pass

    await listener.start(callback=on_status)
    try:
        await stop_future
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await listener.close()
        print("\n👋 监听已停止")


# ==================== 主入口 ====================

async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == "list":
        online_only = "--online" in sys.argv
        await cmd_list(online_only)
    elif cmd == "discover":
        await cmd_discover()
    elif cmd == "listen":
        await cmd_listen()
    elif cmd == "on":
        if len(sys.argv) < 3:
            print("用法: ./main.py on <关键词>")
            return
        await cmd_on_off("on", sys.argv[2])
    elif cmd == "off":
        if len(sys.argv) < 3:
            print("用法: ./main.py off <关键词>")
            return
        await cmd_on_off("off", sys.argv[2])
    elif cmd == "bright":
        if len(sys.argv) < 4:
            print("用法: ./main.py bright <关键词> <0-255>")
            return
        await cmd_bright(sys.argv[2], int(sys.argv[3]))
    elif cmd == "temp":
        if len(sys.argv) < 4:
            print("用法: ./main.py temp <关键词> <2700-6500>")
            return
        await cmd_temp(sys.argv[2], int(sys.argv[3]))
    elif cmd == "curtain":
        if len(sys.argv) < 4:
            print("用法: ./main.py curtain <关键词> <0-100|stop>")
            return
        pos = sys.argv[3]
        if pos.isdigit():
            pos = int(pos)
        await cmd_curtain(sys.argv[2], pos)
    else:
        print(f"❌ 未知命令: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
