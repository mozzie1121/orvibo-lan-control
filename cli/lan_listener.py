"""TCP 状态监听器：连接网关 TCP 8088，被动接收设备状态推送（cmd=42）。

原理：
    建立 TCP 连接 → Hello → Login → 后台循环读包
    网关会通过 TCP 推送设备状态变化（cmd=42，DK_TYPE 加密），
    格式与 readtable 云端 API 的 deviceStatus 完全一致：
    
    - 旧协议（type=38/34/36）：value1, value2, value3, value4
    - ThingModel（type=501/502/503/511）：properties.onoff, properties.brightness 等

用法：
    listener = await TcpStatusListener.create("10.0.0.160", phone, password)
    await listener.start(callback)
"""

import asyncio
import struct
import json
import logging
from typing import Optional, Callable, Dict, Any

from packet import (
    DEFAULT_KEY, ID_UNSET, PK_TYPE, DK_TYPE,
    build_packet, parse_packet,
    CMD_HELLO, CMD_LOGIN, CMD_CONTROL, CMD_HEARTBEAT, CMD_STATE_UPDATE,
    SOFTWARE_VER, SOFTWARE_NAME, SYS_VERSION, HARDWARE_VERSION,
    LANGUAGE, PHONE_NAME, DEBUG_INFO, TCP_PORT,
)

_LOGGER = logging.getLogger(__name__)


def _serial() -> int:
    s = str(int(__import__("time").time() * 1000))
    return int(s[-6:])


def status_to_text(payload: dict) -> str:
    """将 cmd=42 的 payload 转换成可读状态文本。
    复用与 readtable 云端状态一致的解析逻辑（参考 main.py）。"""
    did = payload.get("deviceId", "?")[:16]
    st = payload.get("statusType")
    sdt = payload.get("subDeviceType")
    v1 = payload.get("value1")
    props = payload.get("properties", {}) or {}

    # === ThingModel 格式（有 properties）===
    if props:
        # 多路开关（statusType=511）
        relay = props.get("relay", {})
        if isinstance(relay, dict) and "status" in relay:
            statuses = relay["status"]
            on_count = sum(1 for s in statuses if s == "on")
            return f"[{did}] 多路开关 {on_count}/{len(statuses)} 路开 (st={st}, sdt={sdt})"

        # 单控/调光
        onoff = props.get("onoff", {})
        if isinstance(onoff, dict):
            state = "开" if onoff.get("status") == "on" else "关"
            bri = props.get("brightness", {})
            bri_pct = bri.get("percent") if isinstance(bri, dict) else None
            extra = f" | 亮度 {bri_pct}%" if bri_pct is not None else ""
            return f"[{did}] {state}{extra} (st={st}, sdt={sdt})"

        # 其他 properties
        keys = list(props.keys())
        raw = json.dumps(props, ensure_ascii=False)[:80]
        return f"[{did}] props: {raw} (st={st})"

    # === 旧协议格式（有 value1-4）===
    if v1 is not None:
        state = "开" if v1 == 0 else "关" if v1 == 1 else f"?v1={v1}"
        v2 = payload.get("value2", 0)
        v3 = payload.get("value3", 0)
        v4 = payload.get("value4", 0)
        extra = ""
        if v2 or v3 or v4:
            extra = f" v2={v2} v3={v3} v4={v4}"
        return f"[{did}] {state}{extra} (st={st}, sdt={sdt})"

    return f"[{did}] (st={st}, sdt={sdt}) {json.dumps(payload, ensure_ascii=False)[:100]}"


class TcpStatusListener:
    """TCP 状态监听器。"""

    def __init__(self, host: str, port: int = TCP_PORT,
                 username: str = "", password: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.session_id: Optional[bytes] = None
        self.session_key: Optional[bytes] = None
        self._keys: Dict[bytes, bytes] = {ID_UNSET: DEFAULT_KEY.encode()}
        self._listen_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._packet_count = 0
        self._status_count = 0

    async def _connect(self, timeout: float = 5.0) -> bool:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout)
            self.connected = True
            _LOGGER.info(f"TCP 连接成功 {self.host}:{self.port}")
            return True
        except Exception as e:
            _LOGGER.warning(f"TCP 连接失败 {self.host}:{self.port}: {e}")
            return False

    async def _hello(self) -> bool:
        payload = {
            "source": SOFTWARE_NAME, "softwareVersion": "50103309",
            "sysVersion": SYS_VERSION, "hardwareVersion": HARDWARE_VERSION,
            "language": LANGUAGE, "identifier": hex(int(__import__("time").time()))[2:12],
            "phoneName": PHONE_NAME, "cmd": CMD_HELLO,
            "serial": _serial(), "clientType": 1, "uniSerial": _serial(),
            "serverRecord": False, "ver": SOFTWARE_VER, "debugInfo": DEBUG_INFO,
        }
        self.writer.write(build_packet(PK_TYPE, DEFAULT_KEY.encode(), ID_UNSET, payload))
        await self.writer.drain()

        raw = await self._read_packet(timeout=10.0)
        if raw is None:
            return False
        parsed = parse_packet(raw, self._keys)
        if parsed is None:
            return False
        sid = raw[10:42]
        raw_key = parsed.get("sessionKey") or parsed.get("key")
        if not raw_key:
            _LOGGER.warning(f"Hello 回复无 session key")
            return False
        if isinstance(raw_key, str):
            try:
                self.session_key = bytes.fromhex(raw_key)
            except ValueError:
                self.session_key = raw_key.encode("utf-8")
        else:
            self.session_key = raw_key
        self.session_id = sid
        self._keys[self.session_id] = self.session_key
        _LOGGER.info(f"Hello OK")
        return True

    async def _login(self) -> bool:
        import hashlib
        pwd_md5 = hashlib.md5(self.password.encode()).hexdigest().upper()
        payload = {
            "cmd": CMD_LOGIN, "serial": _serial(),
            "userName": self.username, "password": pwd_md5,
            "clientType": 1, "source": SOFTWARE_NAME,
        }
        self.writer.write(build_packet(DK_TYPE, self.session_key, self.session_id, payload))
        await self.writer.drain()

        raw = await self._read_packet(timeout=10.0)
        if raw is None:
            return False
        parsed = parse_packet(raw, self._keys)
        if parsed is None or parsed.get("status") != 0:
            _LOGGER.warning(f"Login 失败: {parsed}")
            return False
        _LOGGER.info(f"Login OK")
        return True

    async def _read_packet(self, timeout: float = 10.0) -> Optional[bytes]:
        try:
            header = await asyncio.wait_for(self.reader.readexactly(4), timeout=timeout)
            length = struct.unpack(">H", header[2:4])[0]
            rest = await asyncio.wait_for(
                self.reader.readexactly(length - 4), timeout=timeout)
            return header + rest
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, Exception):
            return None

    async def connect(self) -> bool:
        """一键连接 → Hello → Login。"""
        if not await self._connect():
            return False
        if not await self._hello():
            await self.close()
            return False
        if not await self._login():
            await self.close()
            return False
        return True

    async def _heartbeat_loop(self):
        """后台心跳（每 60s）。"""
        while self.connected:
            await asyncio.sleep(60)
            try:
                payload = {
                    "cmd": CMD_HEARTBEAT, "serial": _serial(),
                    "clientType": 1, "uniSerial": _serial(),
                    "serverRecord": False, "ver": SOFTWARE_VER,
                    "debugInfo": DEBUG_INFO,
                }
                self.writer.write(
                    build_packet(DK_TYPE, self.session_key, self.session_id, payload))
                await self.writer.drain()
            except Exception:
                _LOGGER.warning("心跳发送失败")
                self.connected = False
                break

    async def start(self, callback: Optional[Callable[[dict], None]] = None):
        """启动后台监听循环。
        
        持续读 TCP，遇到 cmd=42 就回调。
        同时维护心跳。
        callback 参数: 解析后的 cmd=42 payload dict
        """
        if not self.connected:
            _LOGGER.error("未连接，请先调用 connect()")
            return

        # 启动心跳
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        _LOGGER.info("TCP 状态监听已启动，等待设备状态变化...")

        self._listen_task = asyncio.create_task(
            self._listen_loop(callback), name=f"listen-{self.host}")

    async def _listen_loop(self, callback):
        """后台读取 TCP 数据循环"""
        while self.connected:
            raw = await self._read_packet(timeout=5.0)
            if raw is None:
                # 超时 → 正常，继续等
                if not self.connected:
                    break
                continue

            self._packet_count += 1
            parsed = parse_packet(raw, self._keys)
            if parsed is None:
                continue

            cmd = parsed.get("cmd")
            if cmd == CMD_STATE_UPDATE:
                self._status_count += 1
                _LOGGER.debug(f"cmd=42 #{self._status_count}: {status_to_text(parsed)}")
                if callback:
                    callback(parsed)
            elif cmd in (CMD_HEARTBEAT, 0, 2):
                # 心跳回复、Hello回复、Login回复 → 忽略
                pass
            else:
                _LOGGER.debug(f"跳过 cmd={cmd}")

        _LOGGER.info(f"监听循环结束，共收 {self._packet_count} 包，其中 cmd=42: {self._status_count}")

    async def close(self):
        self.connected = False
        for task in [self._heartbeat_task, self._listen_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        _LOGGER.info("TCP 监听器已关闭")

    @classmethod
    async def create(cls, host: str, username: str, password: str,
                     port: int = TCP_PORT) -> "TcpStatusListener":
        """工厂方法：创建并连接。"""
        obj = cls(host, port, username, password)
        ok = await obj.connect()
        if not ok:
            raise ConnectionError(f"无法连接到 {host}:{port}")
        return obj
