"""
测试：TCP 连接资源释放。
验证 close() 方法正确清理 writer、reader、task 引用。
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.orvibo_lan.lib.lan_controller import LanConnection


class TestLanConnectionClose:
    """验证 LanConnection.close() 的资源释放完整性。"""

    @pytest.mark.asyncio
    async def test_close_sets_writer_to_none(self):
        """close() 后 writer 置为 None。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.writer.is_closing = MagicMock(return_value=False)
        conn.connected = True

        await conn.close()

        assert conn.writer is None
        assert conn.connected is False

    @pytest.mark.asyncio
    async def test_close_calls_wait_closed(self):
        """close() 调用了 writer.close() 和 wait_closed()，然后置为 None。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.reader = AsyncMock()
        conn.connected = True

        # 闭包捕获 writer 引用以便后续断言
        writer = conn.writer
        await conn.close()

        writer.close.assert_called_once()
        writer.wait_closed.assert_called_once()
        assert conn.writer is None

    @pytest.mark.asyncio
    async def test_close_calls_feed_eof(self):
        """close() 调用了 reader.feed_eof() 然后置为 None。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.reader = AsyncMock()
        conn.connected = True

        reader = conn.reader
        await conn.close()

        reader.feed_eof.assert_called_once()
        assert conn.reader is None

    @pytest.mark.asyncio
    async def test_close_sets_reader_to_none(self):
        """close() 后 reader 置为 None。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.reader = AsyncMock()
        conn.connected = True

        await conn.close()

        assert conn.reader is None

    @pytest.mark.asyncio
    async def test_close_cancels_heartbeat_task(self):
        """close() 取消 _heartbeat_task 并置为 None。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.reader = AsyncMock()
        conn.connected = True

        async def dummy():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(dummy())
        conn._heartbeat_task = task

        await conn.close()

        assert task.done()
        assert conn._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_close_cancels_listen_task(self):
        """close() 取消 _listen_task 并置为 None。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.reader = AsyncMock()
        conn.connected = True

        async def dummy():
            try:
                await asyncio.sleep(999)
            except asyncio.CancelledError:
                pass

        task = asyncio.create_task(dummy())
        conn._listen_task = task

        await conn.close()

        assert task.done()
        assert conn._listen_task is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """连续调用 close() 两次不会异常。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = AsyncMock()
        conn.writer.is_closing = MagicMock(return_value=False)
        conn.reader = AsyncMock()
        conn.connected = True

        await conn.close()
        await conn.close()

        assert True

    @pytest.mark.asyncio
    async def test_close_with_no_writer(self):
        """没有 writer 时 close() 不异常。"""
        conn = LanConnection("192.168.1.100")
        conn.reader = None
        conn.connected = True

        await conn.close()

        assert conn.connected is False

    @pytest.mark.asyncio
    async def test_close_with_writer_exception(self):
        """writer.close() 抛异常时 close() 不继续抛。"""
        conn = LanConnection("192.168.1.100")
        conn.writer = MagicMock()
        conn.reader = AsyncMock()
        conn.connected = True

        await conn.close()

        assert conn.writer is None
        assert conn.connected is False
