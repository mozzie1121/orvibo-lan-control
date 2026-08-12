"""Tests for serialized gateway lifecycle and trusted migration."""

import asyncio
from typing import Any

import pytest

from custom_components.orvibo_lan.gateway_manager import GatewayManager
from custom_components.orvibo_lan.lib.discovery import DiscoveryCandidate
from custom_components.orvibo_lan.lib.gateway_connection import GatewayConnectionError


class FakeConnection:
    def __init__(
        self,
        host: str,
        *,
        fail_send: bool = False,
        identity_confirmed: bool = True,
    ) -> None:
        self.host = host
        self.connected = False
        self.identity_confirmed = identity_confirmed
        self.fail_send = fail_send
        self.closed = 0
        self.allow_missing_uid = False
        self.push_callback = None

    async def connect(
        self,
        username: str,
        password: str,
        *,
        expected_uid: str,
        allow_missing_uid: bool = False,
    ) -> None:
        del username, password, expected_uid
        self.allow_missing_uid = allow_missing_uid
        self.connected = True

    async def send(self, payload: object, *, timeout: float | None = None) -> dict[str, Any]:
        del timeout
        await asyncio.sleep(0)
        if self.fail_send:
            self.connected = False
            raise GatewayConnectionError("failed")
        return {"payload": payload}

    async def close(self) -> None:
        self.closed += 1
        self.connected = False

    def set_push_callback(self, callback) -> None:
        self.push_callback = callback


class FakeDiscovery:
    def __init__(self, candidates: dict[str, DiscoveryCandidate]) -> None:
        self.candidates = candidates

    async def discover(self, known_uids: set[str]) -> dict[str, DiscoveryCandidate]:
        assert known_uids == {"uid"}
        return self.candidates


@pytest.mark.asyncio
async def test_send_failure_is_not_retried() -> None:
    created: list[FakeConnection] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host, fail_send=not created)
        created.append(connection)
        return connection

    manager = GatewayManager("user", "password", {"uid": "192.168.1.2"}, connection_factory=factory)
    await manager.ensure("uid")

    with pytest.raises(GatewayConnectionError):
        await manager.send("uid", {"serial": 1})

    assert len(created) == 1
    assert created[0].allow_missing_uid
    await manager.close()
    await manager.close()


@pytest.mark.asyncio
async def test_unconfirmed_candidate_keeps_cloud_host() -> None:
    connections: list[FakeConnection] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host, identity_confirmed=host != "192.168.1.20")
        connections.append(connection)
        return connection

    manager = GatewayManager(
        "user",
        "password",
        {"uid": "192.168.1.2"},
        discovery=FakeDiscovery({"uid": DiscoveryCandidate("uid", "192.168.1.20")}),
        connection_factory=factory,
    )
    await manager.discover()

    assert manager.gateway_hosts["uid"] == "192.168.1.2"
    assert connections[-1].closed >= 1
    assert not connections[-1].allow_missing_uid


@pytest.mark.asyncio
async def test_confirmed_candidate_replaces_cloud_connection() -> None:
    connections: list[FakeConnection] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host)
        connections.append(connection)
        return connection

    manager = GatewayManager(
        "user",
        "password",
        {"uid": "192.168.1.2"},
        discovery=FakeDiscovery({"uid": DiscoveryCandidate("uid", "10.0.0.9")}),
        connection_factory=factory,
    )
    old = await manager.ensure("uid")
    await manager.discover()

    assert manager.gateway_hosts["uid"] == "10.0.0.9"
    assert old.closed == 1
    assert not connections[-1].allow_missing_uid
    await manager.close()


@pytest.mark.asyncio
async def test_cloud_snapshot_removes_and_closes_missing_gateway() -> None:
    connections: list[FakeConnection] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host)
        connections.append(connection)
        return connection

    manager = GatewayManager(
        "user",
        "password",
        {"old": "192.168.1.2", "keep": "192.168.1.3"},
        connection_factory=factory,
    )
    old = await manager.ensure("old")

    await manager.async_update_cloud_gateways({"keep": "192.168.1.3"})

    assert manager.gateway_hosts == {"keep": "192.168.1.3"}
    assert old.closed == 1
    await manager.close()


@pytest.mark.asyncio
async def test_is_connected_tracks_managed_connection() -> None:
    manager = GatewayManager(
        "user",
        "password",
        {"uid": "192.168.1.2"},
        connection_factory=FakeConnection,
    )

    assert not manager.is_connected("uid")
    await manager.ensure("uid")
    assert manager.is_connected("uid")
    await manager.close()
    assert not manager.is_connected("uid")


@pytest.mark.asyncio
async def test_push_callback_is_bound_to_gateway_uid() -> None:
    pushes: list[tuple[str, object]] = []
    manager = GatewayManager(
        "user",
        "password",
        {"gateway-1": "192.168.1.2"},
        connection_factory=FakeConnection,
        push_callback=lambda uid, payload: pushes.append((uid, payload)),
    )

    connection = await manager.ensure("gateway-1")
    assert isinstance(connection, FakeConnection)
    assert connection.push_callback is not None
    payload = {"cmd": 42, "deviceId": "device-1"}
    connection.push_callback(payload)

    assert pushes == [("gateway-1", payload)]
    await manager.close()


@pytest.mark.asyncio
async def test_monitor_reconnects_after_disconnect() -> None:
    created: list[FakeConnection] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host)
        created.append(connection)
        return connection

    manager = GatewayManager(
        "user",
        "password",
        {"uid": "192.168.1.2"},
        connection_factory=factory,
        monitor_interval=0.01,
        max_reconnect_backoff=0.01,
    )
    await manager.ensure("uid")
    await manager.start_monitoring()

    await created[0].close()

    for _ in range(200):
        if len(created) >= 2 and manager.is_connected("uid"):
            break
        await asyncio.sleep(0.01)

    assert manager.is_connected("uid")
    assert len(created) >= 2
    await manager.close()


@pytest.mark.asyncio
async def test_monitor_reports_connectivity_transitions() -> None:
    created: list[FakeConnection] = []
    events: list[tuple[str, bool]] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host)
        created.append(connection)
        return connection

    manager = GatewayManager(
        "user",
        "password",
        {"uid": "192.168.1.2"},
        connection_factory=factory,
        state_callback=lambda uid, connected: events.append((uid, connected)),
        monitor_interval=0.01,
        max_reconnect_backoff=0.01,
    )
    await manager.ensure("uid")
    await manager.start_monitoring()

    for _ in range(200):
        if ("uid", True) in events:
            break
        await asyncio.sleep(0.01)

    await created[0].close()

    for _ in range(400):
        if events.count(("uid", True)) >= 2 and manager.is_connected("uid"):
            break
        await asyncio.sleep(0.01)

    assert ("uid", False) in events
    assert events.count(("uid", True)) >= 2
    assert manager.is_connected("uid")
    await manager.close()


@pytest.mark.asyncio
async def test_close_stops_monitor_reconnect() -> None:
    created: list[FakeConnection] = []

    def factory(host: str) -> FakeConnection:
        connection = FakeConnection(host)
        created.append(connection)
        return connection

    manager = GatewayManager(
        "user",
        "password",
        {"uid": "192.168.1.2"},
        connection_factory=factory,
        monitor_interval=0.01,
        max_reconnect_backoff=0.01,
    )
    await manager.ensure("uid")
    await manager.start_monitoring()

    connection = created[0]
    await manager.close()

    await connection.close()
    await asyncio.sleep(0.05)

    assert len(created) == 1
    assert manager._monitor_tasks == {}
