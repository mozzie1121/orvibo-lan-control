#!/usr/bin/env python3
"""局域网控制核心：UDP发现网关 + TCP连接 + Hello/Login/心跳 + 发送控制命令。"""

import asyncio
import hashlib
import time
import struct
import logging
from typing import Optional, Dict, Any, List

from packet import (
    build_packet, parse_packet, DEFAULT_KEY, ID_UNSET, PK_TYPE, DK_TYPE,
    CMD_HELLO, CMD_LOGIN, CMD_CONTROL, CMD_HEARTBEAT, CMD_STATE_UPDATE,
    SOFTWARE_NAME, SOFTWARE_VERSION, SYS_VERSION, HARDWARE_VERSION,
    LANGUAGE, PHONE_NAME, DEBUG_INFO, SOFTWARE_VER,
    TCP_PORT,
)

_LOGGER = logging.getLogger(__name__)


def _serial() -> int:
    s = str(int(time.time() * 1000))
    return int(s[-6:])


class LanConnection:
    """单个网关的 TCP 连接管理。包含：连接 → Hello → Login → 心跳 → 控制。"""

    def __init__(self, host: str, port: int = TCP_PORT):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.session_id: Optional[bytes] = None
        self.session_key: Optional[bytes] = None
        self._keys: Dict[bytes, bytes] = {ID_UNSET: DEFAULT_KEY.encode()}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._username: Optional[str] = None

    async def connect(self, timeout: float = 5.0) -> bool:
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=timeout,
            )
            self.connected = True
            _LOGGER.info(f"TCP 连接成功 {self.host}:{self.port}")
            return True
        except Exception as e:
            _LOGGER.warning(f"TCP 连接失败 {self.host}:{self.port}: {e}")
            return False

    async def close(self):
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.connected = False
        _LOGGER.info(f"连接已关闭 {self.host}")

    async def hello(self) -> bool:
        """发送 Hello 包，获取 session key。"""
        payload = {
            "source": SOFTWARE_NAME,
            "softwareVersion": SOFTWARE_VERSION,
            "sysVersion": SYS_VERSION,
            "hardwareVersion": HARDWARE_VERSION,
            "language": LANGUAGE,
            "identifier": hex(int(time.time()))[2:12],
            "phoneName": PHONE_NAME,
            "cmd": CMD_HELLO,
            "serial": _serial(),
            "clientType": 1,
            "uniSerial": _serial(),
            "serverRecord": False,
            "ver": SOFTWARE_VER,
            "debugInfo": DEBUG_INFO,
        }
        packet = build_packet(PK_TYPE, DEFAULT_KEY.encode(), ID_UNSET, payload)
        self.writer.write(packet)
        await self.writer.drain()

        raw = await self._read_packet()
        if raw is None:
            return False
        parsed = parse_packet(raw, self._keys)
        if parsed is None:
            return False

        _LOGGER.debug(f"Hello 回复: {parsed}")
        sid = raw[10:42]
        raw_key = parsed.get("sessionKey") or parsed.get("key")
        if not raw_key:
            _LOGGER.warning(f"Hello 回复无 session key: {parsed}")
            return False

        # key 可能是 hex 或纯文本
        if isinstance(raw_key, str):
            try:
                self.session_key = bytes.fromhex(raw_key)
            except ValueError:
                self.session_key = raw_key.encode("utf-8")
        else:
            self.session_key = raw_key

        self.session_id = sid
        self._keys[self.session_id] = self.session_key
        _LOGGER.info(f"Hello OK, session_key 已获取")
        return True

    async def login(self, username: str, password: str) -> bool:
        """发送 Login 包。"""
        self._username = username
        pwd_md5 = hashlib.md5(password.encode()).hexdigest().upper()
        payload = {
            "cmd": CMD_LOGIN,
            "serial": _serial(),
            "userName": username,
            "password": pwd_md5,
            "clientType": 1,
            "source": SOFTWARE_NAME,
        }
        packet = build_packet(DK_TYPE, self.session_key, self.session_id, payload)
        self.writer.write(packet)
        await self.writer.drain()

        raw = await self._read_packet()
        if raw is None:
            return False
        parsed = parse_packet(raw, self._keys)
        if parsed is None:
            return False
        _LOGGER.debug(f"Login 回复: {parsed}")
        status = parsed.get("status")
        if status == 0:
            _LOGGER.info(f"Login OK (网关 {self.host})")
            return True
        else:
            _LOGGER.warning(f"Login 失败: status={status} (网关 {self.host})")
            return False

    async def connect_and_login(self, username: str, password: str,
                                connect_timeout: float = 5.0) -> bool:
        """一键连接 → Hello → Login。"""
        if not await self.connect(connect_timeout):
            return False
        if not await self.hello():
            await self.close()
            return False
        if not await self.login(username, password):
            await self.close()
            return False
        return True

    async def start_heartbeat(self):
        """启动后台心跳任务（每 60s）。"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            return

        async def _hb_loop():
            while self.connected:
                await asyncio.sleep(60)
                try:
                    payload = {
                        "cmd": CMD_HEARTBEAT,
                        "serial": _serial(),
                        "clientType": 1,
                        "uniSerial": _serial(),
                        "serverRecord": False,
                        "ver": SOFTWARE_VER,
                        "debugInfo": DEBUG_INFO,
                    }
                    self.writer.write(
                        build_packet(DK_TYPE, self.session_key, self.session_id, payload)
                    )
                    await self.writer.drain()
                except Exception as e:
                    _LOGGER.warning(f"心跳异常: {e}")
                    break

        self._heartbeat_task = asyncio.create_task(_hb_loop())

    async def send_control(self, payload: dict) -> Optional[dict]:
        """发送 cmd=15 控制命令，并读取网关回复。

        payload 必须包含所有控制参数（cmd/deviceId/uid 等）。
        返回网关回复的 JSON dict，或 None（超时/失败）。
        """
        if not self.connected:
            _LOGGER.error("未连接，无法发送控制命令")
            return None

        # 补全可选字段（不覆盖已有值）
        payload.setdefault("serial", _serial())
        payload.setdefault("uniSerial", _serial())
        payload.setdefault("serverRecord", False)
        payload.setdefault("ver", SOFTWARE_VER)
        payload.setdefault("debugInfo", DEBUG_INFO)
        payload.setdefault("source", SOFTWARE_NAME)

        _LOGGER.debug(f"发送控制命令到 {self.host}: payload={payload}")

        if "cmd" not in payload:
            payload["cmd"] = CMD_CONTROL

        packet = build_packet(DK_TYPE, self.session_key, self.session_id, payload)
        self.writer.write(packet)
        await self.writer.drain()

        # 读取回复：跳过 cmd=42 状态推送，最多读 3 个包
        for attempt in range(3):
            raw = await self._read_packet(timeout=3.0)
            if raw is None:
                return None
            result = parse_packet(raw, self._keys)
            if result is None:
                continue
            recv_cmd = result.get("cmd")
            if recv_cmd == CMD_STATE_UPDATE:
                continue  # 状态推送，不是我们要的回复
            return result
        return None

    async def send_raw_cmd(self, payload: dict) -> Optional[dict]:
        """发送任意 cmd 包（如 cmd=98 晾衣架），不跳过任何回复。"""
        if not self.connected:
            return None

        payload["serial"] = payload.get("serial", _serial())
        payload["uniSerial"] = payload.get("uniSerial", _serial())
        payload["serverRecord"] = payload.get("serverRecord", False)
        payload["ver"] = payload.get("ver", SOFTWARE_VER)
        payload["debugInfo"] = payload.get("debugInfo", DEBUG_INFO)

        packet = build_packet(DK_TYPE, self.session_key, self.session_id, payload)
        self.writer.write(packet)
        await self.writer.drain()

        raw = await self._read_packet(timeout=5.0)
        if raw is None:
            return None
        return parse_packet(raw, self._keys)

    async def _read_packet(self, timeout: float = 10.0) -> Optional[bytes]:
        try:
            header = await asyncio.wait_for(self.reader.readexactly(4), timeout=timeout)
            length = struct.unpack(">H", header[2:4])[0]
            rest = await asyncio.wait_for(
                self.reader.readexactly(length - 4), timeout=timeout
            )
            return header + rest
        except asyncio.TimeoutError:
            _LOGGER.debug("读包超时")
            return None
        except asyncio.IncompleteReadError:
            _LOGGER.debug("读包不完整")
            return None
        except Exception as e:
            _LOGGER.debug(f"读包异常: {e}")
            return None