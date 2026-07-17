"""ORVIBO LAN 协调器：管理网关连接、设备状态、自动发现。"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN, UPDATE_INTERVAL, GATEWAY_DISCOVER_INTERVAL,
    DEVICE_TYPE_MAP, HIDDEN_TYPES,
)
from .lib.https_client import HttpsClient
from .lib.lan_controller import LanConnection
from .lib import device_control as dc

_LOGGER = logging.getLogger(__name__)


class OrviboLanCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Orvibo LAN 协调器。

    职责：
    - 登录云端获取设备列表和网关IP
    - 维护每个网关的 TCP 连接（含心跳保活）
    - 定时 UDP 发现网关，IP 变化时重建连接
    - 定时轮询设备状态
    - 暴露设备控制接口给各平台
    """

    def __init__(self, hass: HomeAssistant, username: str, password: str,
                 family_id: str = None):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=UPDATE_INTERVAL,
        )

        self.username = username
        self.password = password
        self.family_id = family_id

        self.https_client = HttpsClient(username, password, family_id)

        # {gateway_uid: LanConnection}
        self._gateway_connections: Dict[str, LanConnection] = {}
        # {gateway_uid: ip}
        self._gateway_ips: Dict[str, str] = {}
        # 设备列表（last known from readtable）
        self.devices: Dict[str, dict] = {}
        # 设备状态（last known from readtable）
        self.device_states: Dict[str, dict] = {}
        # 设备类型归属（deviceId → device_type）
        self.device_types: Dict[str, int] = {}
        # 网关发现任务
        self._discover_task: Optional[asyncio.Task] = None

    async def _async_setup(self):
        """初始化：登录 + 获取设备列表 + 连接网关。"""
        _LOGGER.info("初始化 Orvibo LAN Coordinator...")

        # 1. 登录（如果还没登录）
        success = await self.https_client.ensure_login()
        if not success:
            raise ConfigEntryAuthFailed("云端登录失败")

        # 2. 获取设备列表和网关信息
        await self._refresh_devices_from_cloud()

        # 3. 连接所有在线网关
        await self._connect_all_gateways()

        # 4. 启动网关发现任务
        self._discover_task = self.hass.async_create_background_task(
            self._gateway_discover_loop(),
            name=f"{DOMAIN}_gateway_discover",
        )

        _LOGGER.info("Orvibo LAN Coordinator 初始化完成")

    async def _async_update_data(self) -> Dict[str, Any]:
        """DataUpdateCoordinator 轮询回调：刷新设备状态。"""
        try:
            await self._refresh_devices_from_cloud()
            return self.device_states
        except Exception as e:
            raise UpdateFailed(f"更新设备状态失败: {e}")

    async def _refresh_devices_from_cloud(self):
        """从云端 API 拉取设备列表和状态。"""
        try:
            devices, statuses, gateways, gateway_ips, _ = \
                await self.https_client.fetch_devices()

            # 更新网关IP映射
            self._gateway_ips = gateway_ips

            # 重建设备索引
            self.devices = {}
            self.device_states = {}
            self.device_types = {}

            for d in devices:
                did = d["deviceId"]
                self.devices[did] = d
                dt_raw = d.get("deviceType", 0)
                self.device_types[did] = int(dt_raw) if isinstance(dt_raw, str) else dt_raw

            for s in statuses.values():
                did = s["deviceId"]
                self.device_states[did] = s

            _LOGGER.debug(f"从云端获取到 {len(self.devices)} 个设备")

        except Exception as e:
            _LOGGER.warning(f"从云端刷新设备失败: {e}")

    async def _connect_all_gateways(self):
        """连接所有已知网关。"""
        for uid, ip in self._gateway_ips.items():
            if uid in self._gateway_connections and \
               self._gateway_connections[uid].connected:
                continue
            try:
                conn = LanConnection(ip)
                ok = await conn.connect_and_login(self.username, self.password)
                if ok:
                    self._gateway_connections[uid] = conn
                    _LOGGER.info(f"网关 {ip} (uid={uid[:12]}...) 连接成功")
                else:
                    _LOGGER.warning(f"网关 {ip} (uid={uid[:12]}...) 连接失败")
            except Exception as e:
                _LOGGER.warning(f"连接网关 {ip} 异常: {e}")

    async def _gateway_discover_loop(self):
        """定时 UDP 发现网关，IP 变化时重建连接。"""
        while True:
            try:
                await asyncio.sleep(GATEWAY_DISCOVER_INTERVAL.total_seconds())

                # UDP 发现
                discovered = await self._udp_discover()
                if not discovered:
                    continue

                # 检查 IP 变化
                for uid, ip in discovered.items():
                    old_ip = self._gateway_ips.get(uid)
                    if old_ip != ip:
                        _LOGGER.info(f"网关 {uid[:12]} IP 变化: {old_ip} → {ip}")
                        self._gateway_ips[uid] = ip

                        # 断开旧连接
                        old_conn = self._gateway_connections.pop(uid, None)
                        if old_conn:
                            await old_conn.close()

                        # 建新连接
                        conn = LanConnection(ip)
                        ok = await conn.connect_and_login(self.username, self.password)
                        if ok:
                            self._gateway_connections[uid] = conn
                            _LOGGER.info(f"网关 {ip} 重新连接成功")

            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.warning(f"网关发现循环异常: {e}")

    async def _udp_discover(self) -> Dict[str, str]:
        """UDP 广播发现网关，返回 {uid: ip}。"""
        import socket
        import time

        from .lib.packet import (build_packet, parse_packet, DEFAULT_KEY,
                                 ID_UNSET, PK_TYPE)

        payload = {
            "cmd": 86,
            "serial": int(str(int(time.time() * 1000))[-6:]),
            "clientType": 1,
            "uniSerial": int(str(int(time.time() * 1000))[-6:]),
            "serverRecord": False,
            "ver": dc.SOFTWARE_VER,
        }
        data = build_packet(PK_TYPE, DEFAULT_KEY.encode(), ID_UNSET, payload)

        loop = asyncio.get_event_loop()

        class Proto(asyncio.DatagramProtocol):
            def __init__(self):
                self.results = {}
            def datagram_received(self, raw, addr):
                parsed = parse_packet(raw, {ID_UNSET: DEFAULT_KEY.encode()})
                if parsed:
                    uid = parsed.get("uid", "")
                    if uid:
                        self.results[uid] = addr[0]

        try:
            trans, proto = await loop.create_datagram_endpoint(
                Proto, family=socket.AF_INET,
                allow_broadcast=True, local_addr=("0.0.0.0", 0),
            )
            trans.sendto(data, ("255.255.255.255", 10000))
            await asyncio.sleep(2.0)
            trans.close()
            return proto.results
        except Exception as e:
            _LOGGER.warning(f"UDP 发现异常: {e}")
            return {}

    async def async_send_raw(self, device_id: str, payload: dict) -> bool:
        """通过 LAN 发送命令（不等待回复，适合空调等不回复的设备）。"""
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.error(f"async_send_raw: 未知设备 {device_id}")
            return False

        uid = device.get("uid", "")
        conn = self._gateway_connections.get(uid)

        if not conn or not conn.connected:
            gw_ip = self._gateway_ips.get(uid)
            if gw_ip:
                conn = LanConnection(gw_ip)
                ok = await conn.connect_and_login(self.username, self.password)
                if ok:
                    self._gateway_connections[uid] = conn
                else:
                    return False
            else:
                return False

        try:
            from .lib.packet import build_packet, DK_TYPE
            pkt = build_packet(DK_TYPE, conn.session_key, conn.session_id, payload)
            conn.writer.write(pkt)
            await conn.writer.drain()
            return True
        except Exception as e:
            _LOGGER.error(f"async_send_raw 失败: {e}")
            if uid in self._gateway_connections:
                await self._gateway_connections[uid].close()
                del self._gateway_connections[uid]
            return False

    async def async_control_device(self, device_id: str, payload: dict) -> bool:
        """通过 LAN 发送控制命令到设备。

        Args:
            device_id: 设备 ID
            payload: 控制 payload（由 device_control 模块生成）

        Returns:
            True 如果控制成功（或设备是空调等不回复的类型）
        """
        device = self.devices.get(device_id)
        if not device:
            _LOGGER.error(f"未知设备: {device_id}")
            return False

        uid = device.get("uid", "")
        dt = self.device_types.get(device_id, 0)
        conn = self._gateway_connections.get(uid)

        if not conn or not conn.connected:
            # 尝试重新连接
            gw_ip = self._gateway_ips.get(uid)
            if gw_ip:
                conn = LanConnection(gw_ip)
                ok = await conn.connect_and_login(self.username, self.password)
                if ok:
                    self._gateway_connections[uid] = conn
                else:
                    _LOGGER.error(f"无法连接网关 {gw_ip}")
                    return False
            else:
                _LOGGER.error(f"找不到设备 {device_id} 所属网关")
                return False

        try:
            # 所有设备统一走 send_control
            result = await conn.send_control(payload)
            if dt == 36:
                # 空调即使没回复也算成功
                return True
            return result is not None and result.get("status") == 0
        except Exception as e:
            _LOGGER.error(f"控制设备 {device_id} 失败: {e}")
            # 标记连接已断开
            if uid in self._gateway_connections:
                await self._gateway_connections[uid].close()
                del self._gateway_connections[uid]
            return False

    async def async_cleanup(self):
        """清理资源：断开所有网关连接、取消任务。"""
        if self._discover_task and not self._discover_task.done():
            self._discover_task.cancel()
            try:
                await self._discover_task
            except asyncio.CancelledError:
                pass

        for uid, conn in list(self._gateway_connections.items()):
            await conn.close()
        self._gateway_connections.clear()

    def get_device_state(self, device_id: str) -> Optional[dict]:
        """获取设备状态。"""
        return self.device_states.get(device_id)
