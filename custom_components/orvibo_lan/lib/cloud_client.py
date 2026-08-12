"""Async client for the Orvibo cloud discovery APIs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Literal, TypeAlias, cast

import aiohttp

from ..exceptions import OrviboLanError
from .packet import HTTPS_HOST, SIGN_KEY, SOFTWARE_VER

_LOGGER = logging.getLogger(__name__)

JsonObject: TypeAlias = dict[str, object]
ObjectList: TypeAlias = list[JsonObject]
StatusMap: TypeAlias = dict[str, JsonObject]
GatewayIpResolver: TypeAlias = Callable[[Mapping[str, object]], str | None]
FetchDevicesResult: TypeAlias = tuple[
    ObjectList,
    StatusMap,
    ObjectList,
    ObjectList,
    dict[str, str],
    GatewayIpResolver,
]
OAuthMethod: TypeAlias = Literal["GET", "POST"]


class CloudClientError(OrviboLanError):
    """Base error for cloud API failures."""


class CloudTransportError(CloudClientError):
    """The cloud request could not be completed."""


class CloudHttpError(CloudClientError):
    """The cloud returned a non-success HTTP status."""

    def __init__(self, operation: str, status: int) -> None:
        super().__init__(f"{operation} returned HTTP {status}")
        self.operation = operation
        self.status = status


class CloudJsonError(CloudClientError):
    """The cloud response was not valid JSON."""


class CloudSchemaError(CloudClientError):
    """The cloud response did not match the expected schema."""


class CloudApiError(CloudClientError):
    """The cloud API reported an application-level error."""


class CloudAuthenticationError(CloudApiError):
    """Authentication failed or returned incomplete credentials."""


class CloudClient:
    """Fetch cloud metadata through an externally owned aiohttp session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        family_id: str | None = None,
        *,
        timeout: aiohttp.ClientTimeout | None = None,
        oauth_method: OAuthMethod = "POST",
    ) -> None:
        if oauth_method not in ("GET", "POST"):
            raise ValueError("oauth_method must be 'GET' or 'POST'")
        self._session = session
        self._username = username
        self._password = password
        self._timeout = timeout or aiohttp.ClientTimeout(
            total=20,
            connect=5,
            sock_read=15,
        )
        self._oauth_method = oauth_method
        self.family_id = family_id
        self.access_token: str | None = None
        self.user_id: str | None = None
        self.family_list: ObjectList = []
        self.family_name = ""

    @property
    def username(self) -> str:
        """Return the account name for migration compatibility."""
        return self._username

    async def ensure_login(self) -> bool:
        """Preserve the legacy boolean login contract."""
        try:
            await self.login()
        except CloudClientError as err:
            _LOGGER.debug("Orvibo cloud login failed (%s)", type(err).__name__)
            return False
        return True

    async def login(self) -> None:
        """Authenticate and populate account and family metadata."""
        password_digest = (
            hashlib.md5(  # noqa: S324 - cloud protocol
                self._password.encode("utf-8")
            )
            .hexdigest()
            .upper()
        )
        credentials = {
            "userName": self._username,
            "type": "0",
            "password": password_digest,
        }
        methods: tuple[OAuthMethod, ...] = (
            ("GET",) if self._oauth_method == "GET" else ("POST", "GET")
        )
        for method in methods:
            try:
                payload = await self._request_json(
                    method,
                    "/getOauthToken",
                    "OAuth login",
                    params=credentials if method == "GET" else None,
                    data=credentials if method == "POST" else None,
                )
                token, user_id = self._parse_oauth_credentials(payload)
            except CloudClientError as err:
                if method != "POST" or not self._should_retry_oauth_with_get(err):
                    raise
                _LOGGER.debug(
                    "OAuth POST response was incompatible (%s); retrying legacy GET",
                    type(err).__name__,
                )
                continue
            self._oauth_method = method
            break
        self.access_token = token
        self.user_id = user_id
        await self.fetch_family_list()

    @classmethod
    def _parse_oauth_credentials(
        cls,
        payload: Mapping[str, object],
    ) -> tuple[str, str]:
        if payload.get("status") != 0 and payload.get("code") != 0:
            raise CloudAuthenticationError("OAuth login was rejected")
        data = cls._require_mapping(payload.get("data"), "OAuth data")
        token = data.get("access_token")
        user_id = data.get("user_id")
        if not isinstance(token, str) or not token:
            raise CloudSchemaError("OAuth data has no access token")
        if not isinstance(user_id, str) or not user_id:
            raise CloudSchemaError("OAuth data has no user ID")
        return token, user_id

    @staticmethod
    def _should_retry_oauth_with_get(error: CloudClientError) -> bool:
        if isinstance(error, CloudHttpError):
            return error.status in {400, 404, 405, 415, 422}
        return isinstance(error, (CloudJsonError, CloudSchemaError))

    async def fetch_family_list(self) -> ObjectList:
        """Fetch families and select the first when none is configured."""
        token, user_id = self._require_credentials()
        params: JsonObject = {
            "accessToken": token,
            "random": uuid.uuid4().hex,
            "timestamp": int(time.time() * 1000),
            "userId": user_id,
        }
        body = dict(params)
        body["sign"] = self._create_sign(params)
        payload = await self._request_json(
            "POST",
            "/v2/family/statistics/users",
            "family list",
            json_body=body,
        )
        self._raise_for_api_error(payload, "family list")

        raw = payload.get("data")
        if isinstance(raw, Mapping):
            family_value = raw.get("familyInfo", [])
        elif isinstance(raw, list):
            family_value = raw
        elif raw is None:
            family_value = []
        else:
            raise CloudSchemaError("family list data must be an object or list")
        families = self._require_object_list(family_value, "family list")
        self.family_list = [
            family
            for family in families
            if isinstance(family.get("familyId"), str) and family["familyId"]
        ]
        if self.family_list:
            first = self.family_list[0]
            name = first.get("familyName", "")
            self.family_name = name if isinstance(name, str) else ""
            if not self.family_id:
                self.family_id = cast(str, first["familyId"])
        return self.family_list

    async def fetch_devices(self) -> FetchDevicesResult:
        """Return the legacy six-item device discovery result."""
        if not self.access_token or not self.user_id:
            await self.login()
        try:
            devices, statuses, gateways, rooms = await self._fetch_readtable()
        except CloudApiError:
            self.access_token = None
            self.user_id = None
            await self.login()
            devices, statuses, gateways, rooms = await self._fetch_readtable()
        gateway_ips = self._build_gateway_ip_map(gateways, devices)

        def resolve(device: Mapping[str, object]) -> str | None:
            uid = device.get("uid", "")
            if isinstance(uid, str) and uid in gateway_ips:
                return gateway_ips[uid]
            return next((ip for ip in gateway_ips.values() if ip), None)

        return devices, statuses, gateways, rooms, gateway_ips, resolve

    async def _fetch_readtable(
        self,
    ) -> tuple[ObjectList, StatusMap, ObjectList, ObjectList]:
        token, user_id = self._require_credentials()
        params: JsonObject = {
            "accessToken": token,
            "dataType": "all",
            "deviceFlag": 0,
            "familyId": self.family_id or os.environ.get("ORVIBO_FAMILY_ID", ""),
            "lastUpdateTime": 0,
            "pageIndex": 0,
            "random": uuid.uuid4().hex,
            "serial": int(str(uuid.uuid4().int)[:9]),
            "sessionId": "",
            "timestamp": int(time.time() * 1000),
            "userId": user_id,
            "userName": self._username,
            "ver": SOFTWARE_VER,
        }
        body = dict(params)
        body["sign"] = self._create_sign(params)
        payload = await self._request_json(
            "POST",
            "/v2/cmd/app/readtable",
            "device list",
            json_body=body,
        )
        self._raise_for_api_error(payload, "device list", require_code=True)
        data = self._require_mapping(payload.get("data"), "device list data")
        devices = self._require_object_list(data.get("device", []), "devices")
        status_items = self._require_object_list(
            data.get("deviceStatus", []),
            "device statuses",
        )
        gateways = self._require_object_list(data.get("gateway", []), "gateways")
        rooms = self._require_object_list(data.get("room", []), "rooms")
        statuses: StatusMap = {}
        for item in status_items:
            device_id = item.get("deviceId")
            if not isinstance(device_id, (str, int)):
                raise CloudSchemaError("device status has no valid deviceId")
            statuses[str(device_id)] = item
        return devices, statuses, gateways, rooms

    async def _request_json(
        self,
        method: OAuthMethod,
        path: str,
        operation: str,
        *,
        params: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
        json_body: JsonObject | None = None,
    ) -> JsonObject:
        try:
            if method == "GET":
                response = await self._session.get(
                    f"https://{HTTPS_HOST}{path}",
                    params=params,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            elif data is not None:
                response = await self._session.post(
                    f"https://{HTTPS_HOST}{path}",
                    data=data,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            elif json_body is not None:
                response = await self._session.post(
                    f"https://{HTTPS_HOST}{path}",
                    json=json_body,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            else:
                response = await self._session.post(
                    f"https://{HTTPS_HOST}{path}",
                    params=params,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
        except (aiohttp.ClientError, asyncio.TimeoutError):
            raise CloudTransportError(f"{operation} request failed") from None

        try:
            if not 200 <= response.status < 300:
                raise CloudHttpError(operation, response.status)
            try:
                payload = await response.json(content_type=None)
            except (ValueError, aiohttp.ClientError) as err:
                raise CloudJsonError(f"{operation} returned invalid JSON") from err
            return self._require_mapping(payload, f"{operation} response")
        finally:
            response.release()

    @staticmethod
    def _require_mapping(value: object, name: str) -> JsonObject:
        if not isinstance(value, Mapping):
            raise CloudSchemaError(f"{name} must be an object")
        return {str(key): item for key, item in value.items()}

    @classmethod
    def _require_object_list(cls, value: object, name: str) -> ObjectList:
        if not isinstance(value, list):
            raise CloudSchemaError(f"{name} must be a list")
        return [cls._require_mapping(item, f"{name} item") for item in value]

    @staticmethod
    def _raise_for_api_error(
        payload: Mapping[str, object],
        operation: str,
        *,
        require_code: bool = False,
    ) -> None:
        code = payload.get("code")
        if (require_code and code != 0) or (code is not None and code != 0):
            raise CloudApiError(f"{operation} was rejected")
        status = payload.get("status")
        if status is not None and status != 0:
            raise CloudApiError(f"{operation} was rejected")

    def _require_credentials(self) -> tuple[str, str]:
        if not self.access_token or not self.user_id:
            raise CloudAuthenticationError("cloud credentials are unavailable")
        return self.access_token, self.user_id

    @staticmethod
    def _create_sign(params: Mapping[str, object]) -> str:
        parts = [
            f"{key}={params[key]}&"
            for key in sorted(params)
            if params[key] is not None and str(params[key]).strip()
        ]
        parts.append(f"key={SIGN_KEY}")
        return (
            hmac.new(
                SIGN_KEY.encode(),
                "".join(parts).encode(),
                hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )

    @staticmethod
    def _build_gateway_ip_map(
        gateways: ObjectList,
        devices: ObjectList,
    ) -> dict[str, str]:
        mixpad_uids = {
            uid
            for device in devices
            if device.get("deviceType") in (114, 510)
            and isinstance((uid := device.get("uid")), str)
            and uid
        }
        result: dict[str, str] = {}
        for gateway in gateways:
            uid = gateway.get("uid")
            raw_ip = gateway.get("localStaticIP") or gateway.get("ip")
            if isinstance(uid, str) and uid in mixpad_uids and isinstance(raw_ip, str) and raw_ip:
                result[uid] = raw_ip.split(":", maxsplit=1)[0]
        return result
