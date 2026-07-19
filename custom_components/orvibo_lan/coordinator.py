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

# 安全上限
_MAX_DEVICES = 1000      # 设备列表上限，防止异常数据导致内存溢出
_MAX_LAN_PROPS = 200      # LAN 推送缓存上限

# 状态更新中只增量更新的字段（避免全量替换）
_INCR_UPDATE_KEYS = frozenset((
    "value1", "value2", "value3", "value4",
    "statusType", "subDeviceType",
    "alarmType", "online", "updateTime",
))


class OrviboLanCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Orvibo LAN 协调器。

    职责：
    - 登录云端获取设备列表和网关IP
    - 维护每个网关的 TCP 连接（含心跳保活）
    - 定时 UDP 发现网关，IP 变化时重建连接
    - 定时轮询设备状态
    - 暴露设备控制接口给各平台
    """

    __slots__ = (
        "username", "password", "family_id",
        "https_client",
        "_gateway_connections", "_gateway_ips",
        "_lan_properties", "_lan_properties_order",
        "devices", "device_states", "device_types",
        "room_names", "_discover_task",
        "_debounce_timer", "_notify_task",
        "_heartbeat_tasks",
    )

    def __init__(self, hass: HomeAssistant, username: str, password: str,
                 family_id: str = None):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator",
            update_interval=None,  # 关闭轮询，全靠局域网 cmd=42 推送
        )

        self.username = username
        self.password = password
        self.family_id = family_id

        self.https_client = HttpsClient(username, password, family_id)

        # {gateway_uid: LanConnection}
        self._gateway_connections: Dict[str, LanConnection] = {}
        # {gateway_uid: ip}
        self._gateway_ips: Dict[str, str] = {}
        # LAN 推送属性缓存（cmd=42 增量合并，不受云端轮询覆盖）
        self._lan_properties: Dict[str, dict] = {}
        # LAN 推送属性插入顺序（用于 LRU 淘汰）
        self._lan_properties_order: list = []
        # 设备列表（last known from readtable）
        self.devices: Dict[str, dict] = {}
        # 设备状态（last known from readtable）
        self.device_states: Dict[str, dict] = {}
        # 设备类型归属（deviceId → device_type）
        self.device_types: Dict[str, int] = {}
        # 房间映射（roomId → roomName）
        self.room_names: Dict[str, str] = {}
        # 网关发现任务
        self._discover_task: Optional[asyncio.Task] = None

        # 节流通知字段
        self._debounce_timer: Optional[asyncio.TimerHandle] = None
        self._notify_task: Optional[asyncio.Task] = None
        # {gateway_uid: asyncio.Task} 心跳任务追踪，用于安全取消
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

    async def _async_setup(self):
        """初始化：登录 + 获取设备列表 + 连接网关。"""
        _LOGGER.debug("初始化 Orvibo LAN Coordinator...")

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

        _LOGGER.debug("Orvibo LAN Coordinator 初始化完成")

    async def _async_update_data(self) -> Dict[str, Any]:
        """DataUpdateCoordinator 轮询回调：禁用轮询，直接返回当前状态。"""
        return self.device_states

    async def _refresh_devices_from_cloud(self):
        """从云端 API 拉取设备列表和状态。"""
        try:
            devices, statuses, gateways, rooms, gateway_ips, _ = \
                await self.https_client.fetch_devices()

            # 更新网关IP映射
            self._gateway_ips = gateway_ips

            # 解析房间映射
            self.room_names = {}
            for r in rooms:
                rid = r.get("roomId", "")
                if rid:
                    self.room_names[rid] = r.get("roomName", "")

            # 安全上限检查
            if len(devices) > _MAX_DEVICES:
                _LOGGER.warning(
                    f"云端返回设备数 {len(devices)} 超过上限 {_MAX_DEVICES}，已截断"
                )
                devices = devices[:_MAX_DEVICES]

            # 重建索引（同时清理已不存在设备的 _lan_properties）
            new_devices = {}
            new_device_states = {}
            new_device_types = {}

            for d in devices:
                did = d["deviceId"]
                new_devices[did] = d
                dt_raw = d.get("deviceType", 0)
                new_device_types[did] = int(dt_raw) if isinstance(dt_raw, str) else dt_raw

            for s in statuses.values():
                did = s["deviceId"]
                if did in new_devices:
                    new_device_states[did] = s

            self.devices = new_devices
            self.device_states = new_device_states
            self.device_types = new_device_types

            # 清理不再存在的设备的 LAN 缓存
            stale_lan = [k for k in self._lan_properties if k not in new_devices]
            for k in stale_lan:
                self._lan_properties.pop(k, None)
                if k in self._lan_properties_order:
                    self._lan_properties_order.remove(k)
            if stale_lan:
                _LOGGER.debug(f"清理了 {len(stale_lan)} 个过期 LAN 缓存条目")

            _LOGGER.debug(f"从云端获取到 {len(self.devices)} 个设备")

            # 初始化传感器状态（从云端 deviceStatus 的 value1-value4 解析触发状态/电量/温湿度）
            for did, state in self.device_states.items():
                self._parse_sensor_state(state, did)

        except Exception as e:
            _LOGGER.debug(f"从云端刷新设备失败: {e}")

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
                    # 启动心跳任务并追踪
                    self._heartbeat_tasks[uid] = asyncio.create_task(
                        self._heartbeat_loop(uid, conn)
                    )
                    # 启动状态监听循环，捕获 cmd=42 推送
                    # 监听循环在同个事件循环中运行，直接同步回调
                    conn.start_listen_loop(self._on_status_update)
                    _LOGGER.debug(f"网关 {ip} (uid={uid[:12]}...) 连接成功，状态监听已启动")
                else:
                    _LOGGER.debug(f"网关 {ip} (uid={uid[:12]}...) 连接失败")
            except Exception as e:
                _LOGGER.debug(f"连接网关 {ip} 异常: {e}")

    async def _heartbeat_loop(self, uid: str, conn: LanConnection):
        """网关心跳任务（后台运行，可被安全取消和追踪）。

        Args:
            uid: 网关 UID（用于任务追踪）
            conn: LanConnection 实例
        """
        try:
            while conn.connected:
                await asyncio.sleep(60)
                try:
                    from .lib.packet import (
                        build_packet, DK_TYPE, CMD_HEARTBEAT, SOFTWARE_VER, DEBUG_INFO,
                    )

                    def _serial() -> int:
                        s = str(int(time.time() * 1000))
                        return int(s[-6:])

                    payload = {
                        "cmd": CMD_HEARTBEAT,
                        "serial": _serial(),
                        "clientType": 1,
                        "uniSerial": _serial(),
                        "serverRecord": False,
                        "ver": SOFTWARE_VER,
                        "debugInfo": DEBUG_INFO,
                    }
                    conn.writer.write(
                        build_packet(DK_TYPE, conn.session_key, conn.session_id, payload)
                    )
                    await conn.writer.drain()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    _LOGGER.debug(f"心跳异常 ({uid[:12]}): {e}")
                    break
        except asyncio.CancelledError:
            _LOGGER.debug(f"心跳任务被取消 ({uid[:12]})")
        finally:
            # 从追踪字典中清理自身引用
            if uid in self._heartbeat_tasks and \
               self._heartbeat_tasks[uid] is asyncio.current_task():
                del self._heartbeat_tasks[uid]

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
                        _LOGGER.debug(f"网关 {uid[:12]} IP 变化: {old_ip} → {ip}")
                        self._gateway_ips[uid] = ip

                        # 断开旧连接（含心跳任务清理）
                        old_conn = self._gateway_connections.pop(uid, None)
                        await self._cancel_heartbeat(uid)
                        if old_conn:
                            await old_conn.close()

                        # 建新连接
                        conn = LanConnection(ip)
                        ok = await conn.connect_and_login(self.username, self.password)
                        if ok:
                            self._gateway_connections[uid] = conn
                            self._heartbeat_tasks[uid] = asyncio.create_task(
                                self._heartbeat_loop(uid, conn)
                            )
                            _LOGGER.debug(f"网关 {ip} 重新连接成功")

            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.debug(f"网关发现循环异常: {e}")

    async def _cancel_heartbeat(self, uid: str):
        """安全取消指定网关的心跳任务。"""
        task = self._heartbeat_tasks.pop(uid, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

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
            _LOGGER.debug(f"UDP 发现异常: {e}")
            return {}

    def _on_status_update(self, payload: dict):
        """TCP 监听循环回调：收到 cmd=42 状态推送，更新本地状态缓存。

        在 hass 事件循环线程中执行（通过 call_soon_threadsafe 调用）。
        cmd=42 的格式与 readtable 云端返回的 deviceStatus 完全一致：
        - 旧协议: value1, value2, value3, value4
        - ThingModel: properties.onoff, properties.brightness 等
        区别：cmd=42 没有 online 字段，但有 statusType/subDeviceType。
        """
        did = payload.get("deviceId")
        if not did:
            return

        old_state = self.device_states.get(did, {})

        # 增量更新普通字段（不创建新 dict，直接原地 update）
        changed = False
        for key in _INCR_UPDATE_KEYS:
            if key in payload and payload[key] != old_state.get(key):
                old_state[key] = payload[key]
                changed = True

        # 处理 LAN properties 增量合并
        incoming_props = payload.get("properties")
        if incoming_props and isinstance(incoming_props, dict):
            old_lan = self._lan_properties.get(did)
            if old_lan is None:
                # 新设备，创建条目并记录插入顺序
                self._lan_properties[did] = dict(incoming_props)
                self._lan_properties_order.append(did)
                changed = True
            else:
                # 增量更新（仅更新变化的字段）
                for k, v in incoming_props.items():
                    if v is not None and old_lan.get(k) != v:
                        old_lan[k] = v
                        changed = True

            # LRU 淘汰策略：超出上限时删除最旧条目
            while len(self._lan_properties) > _MAX_LAN_PROPS:
                oldest = self._lan_properties_order.pop(0)
                self._lan_properties.pop(oldest, None)
                _LOGGER.debug(f"LAN 缓存淘汰 (>= {_MAX_LAN_PROPS}): {oldest[:16]}..")

            # 写入 device_states，但只存引用而非深拷贝——避免 GC 压力
            old_state["properties"] = self._lan_properties[did]

        if changed:
            _LOGGER.debug(f"cmd=42 更新: {did[:16]}.. props={payload.get('value1', payload.get('properties', '?'))}")

        # 解析传感器状态（门窗/人体/烟雾/燃气/水浸/紧急按钮/温湿度）
        self._parse_sensor_state(old_state, did)

        # 节流通知：200ms 内多次 cmd=42 合并为一次通知
        # 避免高频推送挤爆 HA 事件循环
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        if self._notify_task is not None and not self._notify_task.done():
            self._notify_task.cancel()
            self._notify_task = None

        self._notify_task = asyncio.create_task(self._debounced_notify())

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
            if dt in (36, 81):
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
        self._discover_task = None

        # 取消所有心跳任务
        for uid in list(self._heartbeat_tasks.keys()):
            await self._cancel_heartbeat(uid)

        # 断开所有网关连接
        for uid, conn in list(self._gateway_connections.items()):
            await conn.close()
        self._gateway_connections.clear()

        # 清空缓存
        self._lan_properties.clear()
        self._lan_properties_order.clear()
        self.devices.clear()
        self.device_states.clear()
        self.device_types.clear()
        self.room_names.clear()

        _LOGGER.debug("协调器资源已全部清理")

    def get_device_state(self, device_id: str) -> Optional[dict]:
        """获取设备状态（含 LAN 推送的属性覆盖）。"""
        base = self.device_states.get(device_id)
        if not base:
            return None
        # 如果 _lan_properties 有数据，覆盖到 base 上
        lan_props = self._lan_properties.get(device_id)
        if lan_props:
            base = dict(base)
            base["properties"] = dict(lan_props)
        return base

    def get_room_name(self, device_id: str) -> Optional[str]:
        """获取设备所属房间名。

        Args:
            device_id: 设备 ID

        Returns:
            房间名，如果没有则返回 None
        """
        device = self.devices.get(device_id)
        if not device:
            return None

        room_id = device.get("roomId", "")
        if room_id and room_id in self.room_names:
            return self.room_names[room_id]

        device_state = self.get_device_state(device_id)
        if device_state:
            props = device_state.get("properties", {})
            descriptor = props.get("Descriptor", {})
            room_id_from_state = descriptor.get("roomId", "")
            if room_id_from_state and room_id_from_state in self.room_names:
                return self.room_names[room_id_from_state]

        room_name = device.get("roomName")
        return room_name if room_name else None

    def _parse_sensor_state(self, state: dict, device_id: str) -> None:
        """解析传感器触发状态（参照 orvibohomebridge coordinator 的 _parse_status_* 系列方法）。

        传感器数据来自 TCP cmd=42 推送（value1-value4 格式），在 _on_status_update 中被调用。
        dataType 格式约定：
        - 门窗(46): value1=1 开, value4=电量
        - 人体(26): value3=1 触发, value4=电量
        - 烟雾(27)/燃气(25)/水浸(54): value1=1 告警, value4=电量
        - 紧急按钮(56): value1=1 按下, value4=电量
        - 温湿度(22/23): value1=温度, value2=湿度, value4=电量
        """
        dt = self.device_types.get(device_id, 0)

        # 从 state 取原始值，兼容 int/str
        def _int(v):
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        v1 = _int(state.get("value1"))
        v2 = _int(state.get("value2"))
        v3 = _int(state.get("value3"))
        v4 = _int(state.get("value4"))

        if dt == 46:  # 门窗传感器
            if v1 is not None:
                state["door_state"] = v1 == 1

        elif dt == 26:  # 人体传感器
            if v3 is not None:
                state["motion_detected"] = v3 == 1

        elif dt in (27, 25, 54):  # 烟雾/燃气/水浸
            if v1 is not None:
                if dt == 27:
                    state["smoke_detected"] = v1 == 1
                elif dt == 25:
                    state["gas_detected"] = v1 == 1
                elif dt == 54:
                    state["water_leak_detected"] = v1 == 1

        elif dt == 56:  # 紧急按钮
            if v1 is not None:
                state["emergency_state"] = v1 == 1

        # 所有传感器：value4 为电量百分比
        if v4 is not None and 0 <= v4 <= 100:
            state["battery"] = v4

        # 温湿度：value1=温度, value2=湿度（标量或编码值）
        if dt in (22, 23):
            if v1 is not None:
                state["temperature"] = float(v1)
            if v2 is not None:
                state["humidity"] = float(v2)

    async def _debounced_notify(self):
        """节流通知：等待 200ms 后触发 HA 状态更新。"""
        try:
            await asyncio.sleep(0.2)
            self._debounce_timer = None
            self.async_set_updated_data(self.device_states)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
