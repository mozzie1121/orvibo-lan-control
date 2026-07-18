"""
测试：协调器的内存管理和资源释放。
验证 Task 追踪、心跳取消、缓存上限、增量更新。
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from custom_components.orvibo_lan.coordinator import OrviboLanCoordinator, _MAX_DEVICES, _MAX_LAN_PROPS


@pytest.fixture
def event_loop():
    """为需要 asyncio 事件的测试创建 event loop。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


class FakeHass:
    """模拟 HomeAssistant 核心对象的最小实现。"""
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.data = {}
        self.config = MagicMock()
        self.states = MagicMock()

    def async_create_background_task(self, coro, name):
        return asyncio.ensure_future(coro)


class TestCoordinatorHeartbeatTasks:
    """验证心跳 Task 的生命周期管理。"""

    @pytest.mark.asyncio
    async def test_heartbeat_task_tracked(self):
        """创建心跳后 _heartbeat_tasks 有记录。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        uid = "test_uid_1234"

        async def mock_heartbeat():
            coord._heartbeat_tasks[uid] = asyncio.current_task()
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                pass
            finally:
                if uid in coord._heartbeat_tasks:
                    del coord._heartbeat_tasks[uid]

        task = asyncio.create_task(mock_heartbeat())
        coord._heartbeat_tasks[uid] = task
        await asyncio.sleep(0.01)

        assert uid in coord._heartbeat_tasks
        assert not coord._heartbeat_tasks[uid].done()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert uid not in coord._heartbeat_tasks

    @pytest.mark.asyncio
    async def test_cancel_heartbeat_removes_tracking(self):
        """_cancel_heartbeat() 后追踪字典中已移除。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        uid = "test_uid_cancel"

        async def dummy():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(dummy())
        coord._heartbeat_tasks[uid] = task

        await coord._cancel_heartbeat(uid)

        assert uid not in coord._heartbeat_tasks
        assert task.done()

    @pytest.mark.asyncio
    async def test_cancel_heartbeat_nonexistent(self):
        """取消不存在的 uid 不报错。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        await coord._cancel_heartbeat("nonexistent")
        assert True

    @pytest.mark.asyncio
    async def test_async_cleanup_cancels_all_heartbeats(self):
        """async_cleanup() 取消所有心跳任务。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        uids = ["gw1", "gw2"]
        tasks = []

        for uid in uids:
            async def dummy():
                try:
                    await asyncio.sleep(999)
                except asyncio.CancelledError:
                    pass
            t = asyncio.create_task(dummy())
            coord._heartbeat_tasks[uid] = t
            tasks.append(t)
            conn = AsyncMock()
            coord._gateway_connections[uid] = conn

        await coord.async_cleanup()

        assert len(coord._heartbeat_tasks) == 0
        for t in tasks:
            assert t.done()


class TestCoordinatorStateUpdate:
    """验证 _on_status_update 增量更新逻辑。"""

    @pytest.mark.asyncio
    async def test_incremental_update_preserves_unrelated_fields(self):
        """增量更新不丢失未修改的字段。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        did = "device_001"

        coord.device_states[did] = {
            "deviceId": did,
            "value1": 0,
            "value2": 255,
            "order": "on",
        }

        coord._on_status_update({
            "deviceId": did,
            "value1": 1,
        })

        state = coord.device_states[did]
        assert state["value1"] == 1
        assert state["value2"] == 255
        assert state["order"] == "on"

    @pytest.mark.asyncio
    async def test_incremental_update_properties(self):
        """properties 增量更新只修改变化的字段。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        did = "device_002"

        coord._lan_properties[did] = {
            "onoff": {"status": "off"},
            "brightness": {"percent": 50},
        }
        coord._lan_properties_order.append(did)

        coord._on_status_update({
            "deviceId": did,
            "properties": {"onoff": {"status": "on"}},
        })

        props = coord._lan_properties[did]
        assert props["onoff"] == {"status": "on"}
        assert props["brightness"] == {"percent": 50}

    @pytest.mark.asyncio
    async def test_new_device_creates_lan_entry(self):
        """新设备创建 _lan_properties 条目。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        did = "new_device"

        coord._on_status_update({
            "deviceId": did,
            "properties": {"onoff": {"status": "on"}},
        })

        assert did in coord._lan_properties
        assert coord._lan_properties[did]["onoff"] == {"status": "on"}

    @pytest.mark.asyncio
    async def test_none_property_value_skipped(self):
        """None 值的 property 跳过更新。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")
        did = "device_none_test"

        coord._lan_properties[did] = {"onoff": {"status": "on"}}
        coord._lan_properties_order.append(did)

        coord._on_status_update({
            "deviceId": did,
            "properties": {"onoff": None},
        })

        assert coord._lan_properties[did]["onoff"] == {"status": "on"}


class TestCoordinatorCacheLimit:
    """验证缓存上限保护。"""

    @pytest.mark.asyncio
    async def test_lan_properties_lru_eviction(self):
        """_lan_properties 超出上限后淘汰最旧条目。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")

        for i in range(_MAX_LAN_PROPS + 20):
            did = f"device_{i:04d}"
            coord._lan_properties[did] = {"onoff": {"status": "off"}}
            coord._lan_properties_order.append(did)

        coord._on_status_update({
            "deviceId": "trigger_device",
            "properties": {"onoff": {"status": "on"}},
        })

        assert len(coord._lan_properties) <= _MAX_LAN_PROPS + 1
        assert "device_0000" not in coord._lan_properties

    @pytest.mark.asyncio
    async def test_refresh_devices_cleans_stale_lan(self):
        """_refresh_devices_from_cloud() 清理已不存在设备的 LAN 缓存。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")

        coord._lan_properties["stale_device_1"] = {}
        coord._lan_properties["stale_device_2"] = {}
        coord._lan_properties_order.extend(["stale_device_1", "stale_device_2"])

        coord.https_client.fetch_devices = AsyncMock(return_value=(
            [], {}, [], {}, {}, set()
        ))

        await coord._refresh_devices_from_cloud()

        assert "stale_device_1" not in coord._lan_properties
        assert "stale_device_2" not in coord._lan_properties

    @pytest.mark.asyncio
    async def test_refresh_devices_device_limit(self):
        """云端返回超上限设备时截断。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")

        too_many_devices = [
            {"deviceId": f"d_{i}"} for i in range(_MAX_DEVICES + 100)
        ]
        coord.https_client.fetch_devices = AsyncMock(return_value=(
            too_many_devices, {}, [], {}, {}, set()
        ))

        await coord._refresh_devices_from_cloud()

        assert len(coord.devices) <= _MAX_DEVICES


class TestCoordinatorCleanup:
    """验证清理完整性。"""

    @pytest.mark.asyncio
    async def test_async_cleanup_clears_all_caches(self):
        """async_cleanup() 清空所有缓存。"""
        coord = OrviboLanCoordinator(FakeHass(), "user", "pass")

        coord._lan_properties["d1"] = {}
        coord._lan_properties_order.append("d1")
        coord.devices["d1"] = {}
        coord.device_states["d1"] = {}
        coord.device_types["d1"] = 1
        coord.room_names["room1"] = "客厅"

        await coord.async_cleanup()

        assert len(coord._lan_properties) == 0
        assert len(coord._lan_properties_order) == 0
        assert len(coord.devices) == 0
        assert len(coord.device_states) == 0
        assert len(coord.device_types) == 0
        assert len(coord.room_names) == 0
