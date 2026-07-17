#!/usr/bin/env python3
"""HTTPS REST API 客户端：获取设备列表 + 网关IP映射。

通过 Orvibo 云端 API 获取用户账户下的所有设备、网关信息（含局域网 IP）。
只用于获取设备列表和网关IP，控制走局域网 TCP 8088。
"""

import json
import time
import os
import uuid
import hmac
import hashlib
import logging
from typing import Optional

import aiohttp

from packet import HTTPS_HOST, SIGN_KEY, SOFTWARE_VER

_LOGGER = logging.getLogger(__name__)


class HttpsClient:
    """通过 HTTPS 获取设备列表和网关信息。"""

    def __init__(self, username: str, password: str, family_id: str = None):
        self.username = username
        self.password = password
        self.family_id = family_id

        self.access_token: Optional[str] = None
        self.user_id: Optional[str] = None

    async def _ensure_token(self, session: aiohttp.ClientSession):
        """获取 access_token（含登录）。"""
        if self.access_token:
            return

        pwd_md5 = hashlib.md5(self.password.encode()).hexdigest().upper()
        url = f"https://{HTTPS_HOST}/getOauthToken?userName={self.username}&type=0&password={pwd_md5}"
        resp = await session.get(url)
        j = json.loads(await resp.text())

        if j.get("status") != 0 and j.get("code") != 0:
            raise RuntimeError(f"登录失败: {j}")

        data = j.get("data", {})
        self.access_token = data.get("access_token")
        self.user_id = data.get("user_id")
        _LOGGER.info(f"已获取 access_token, user_id={self.user_id}")

    @staticmethod
    def _create_sign(params: dict) -> str:
        """HMAC 签名：排序、拼接、排除空值、追加 key。"""
        sorted_keys = sorted(params.keys())
        sb = []
        for k in sorted_keys:
            v = params[k]
            if v is not None and str(v).strip() != "":
                sb.append(f"{k}={v}&")
        sb.append(f"key={SIGN_KEY}")
        return hmac.new(SIGN_KEY.encode(), "".join(sb).encode(),
                        hashlib.sha256).hexdigest().upper()

    async def fetch_devices(self):
        """获取设备列表和网关信息。

        Returns:
            (devices, statuses, gateways, gateway_ips, get_gateway_ip_for_device)
        """
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        ) as session:
            await self._ensure_token(session)
            devices, statuses, gateways = await self._fetch_readtable(session)

        # 建立 gatewayId → IP 映射
        gateway_ips = self._build_gateway_ip_map(gateways, devices)

        # 找设备归属网关的函数
        def get_gateway_ip_for_device(dev: dict) -> Optional[str]:
            dev_uid = dev.get("uid", "")
            if dev_uid in gateway_ips:
                return gateway_ips[dev_uid]
            for gid, ip in gateway_ips.items():
                if ip:
                    return ip
            return None

        return devices, statuses, gateways, gateway_ips, get_gateway_ip_for_device

    async def _fetch_readtable(self, session: aiohttp.ClientSession):
        """获取完整设备列表（含网关信息）。

        通过 /v2/cmd/app/readtable API 获取。
        family_id 优先级：构造参数 > 环境变量 ORVIBO_FAMILY_ID > 空字符串
        """
        # family_id 获取策略
        family_id = self.family_id or os.environ.get("ORVIBO_FAMILY_ID", "")

        rand = uuid.uuid4().hex
        ts = int(time.time() * 1000)
        serial_v = int(str(uuid.uuid4().int)[:9])

        params = {
            "accessToken": self.access_token,
            "dataType": "all",
            "deviceFlag": 0,
            "familyId": family_id,
            "lastUpdateTime": 0,
            "pageIndex": 0,
            "random": rand,
            "serial": serial_v,
            "sessionId": "",
            "timestamp": ts,
            "userId": self.user_id,
            "userName": self.username,
            "ver": SOFTWARE_VER,
        }
        sign = self._create_sign(params)

        data = dict(params)
        data["sign"] = sign

        resp = await session.post(
            f"https://{HTTPS_HOST}/v2/cmd/app/readtable",
            json=data
        )
        j = await resp.json(content_type=None)

        if j.get("code") != 0:
            raise RuntimeError(f"获取设备列表失败: {j}")

        dd = j.get("data", {})
        devices = dd.get("device", [])
        statuses = {s["deviceId"]: s for s in dd.get("deviceStatus", [])}
        gateways = dd.get("gateway", [])

        return devices, statuses, gateways

    def _build_gateway_ip_map(self, gateways: list, devices: list) -> dict:
        """建立 uid → IP 的映射。

        readtable API 返回的 gateway 数据含 localStaticIP。
        """
        gateway_ips = {}

        for g in gateways:
            gw_uid = g.get("uid", "")
            ip = g.get("localStaticIP", "") or g.get("ip", "")
            if ip and ":" in ip:
                ip = ip.split(":")[0]
            if gw_uid and ip:
                gateway_ips[gw_uid] = ip

        # 也尝试从 type=114 设备匹配
        for d in devices:
            if d.get("deviceType") == 114:
                uid = d.get("uid", "")
                if uid and uid not in gateway_ips:
                    # 回退：在网关列表中找同 uid 的 IP
                    for g in gateways:
                        if g.get("uid") == uid:
                            ip = g.get("localStaticIP", "") or g.get("ip", "")
                            if ip:
                                if ":" in ip:
                                    ip = ip.split(":")[0]
                                gateway_ips[uid] = ip
                            break

        return gateway_ips
