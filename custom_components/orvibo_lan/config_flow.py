"""ORVIBO LAN Control 配置流：输入账号→选择家庭→选择设备→完成。"""

import logging
import re
from typing import Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_FAMILY_ID, CONF_SELECTED_DEVICE_IDS
from .selection import selected_device_ids

_LOGGER = logging.getLogger(__name__)


def _device_label(device_id: str, name: str, room: str) -> str:
    """短标签：设备名 + 房间名"""
    if room and room != name:
        return f"{name} [{room}]"
    return name or device_id[-8:]


def _device_schema(devices: list[dict]) -> vol.Schema:
    """多选设备表单。"""
    options = [
        selector.SelectOptionDict(
            value=str(dev["deviceId"]),
            label=_device_label(
                dev["deviceId"],
                dev.get("deviceName", ""),
                dev.get("roomName", ""),
            ),
        )
        for dev in devices
    ]
    # 默认全选
    default_ids = [str(dev["deviceId"]) for dev in devices]
    return vol.Schema({
        vol.Required(CONF_SELECTED_DEVICE_IDS, default=default_ids): (
            selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        )
    })


class OrviboLanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._family_list: list = []
        self._family_name: str = ""
        self._selected_family_id: Optional[str] = None
        self._user_id: str = ""
        self._devices: list[dict] = []
        self._https_client = None

    async def async_step_user(
        self, user_input: Optional[dict] = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            if not username or not password:
                errors["base"] = "empty_username_or_password"
            else:
                try:
                    from .lib.https_client import HttpsClient

                    client = HttpsClient(username, password)
                    success = await client.ensure_login()

                    if success:
                        self._username = username
                        self._password = password
                        self._family_list = client.family_list
                        self._family_name = client.family_name
                        self._user_id = client.user_id
                        self._https_client = client

                        if len(self._family_list) <= 1:
                            family_id = (
                                self._family_list[0]["familyId"]
                                if self._family_list
                                else None
                            )
                            self._selected_family_id = family_id
                            return await self.async_step_devices()
                        else:
                            return await self.async_step_select_family()
                    else:
                        errors["base"] = "auth_failed"
                except Exception as e:
                    _LOGGER.error(f"登录失败: {e}", exc_info=True)
                    errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_select_family(
        self, user_input: Optional[dict] = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            family_id = user_input.get(CONF_FAMILY_ID)
            if family_id:
                self._selected_family_id = family_id
                for f in self._family_list:
                    if f["familyId"] == family_id:
                        self._family_name = f.get("familyName", "")
                        break
                return await self.async_step_devices()

        family_choices = {
            f["familyId"]: f"{f['familyName']} ({f['familyId'][:8]}...)"
            for f in self._family_list
        }

        return self.async_show_form(
            step_id="select_family",
            data_schema=vol.Schema({
                vol.Required(CONF_FAMILY_ID): vol.In(family_choices),
            }),
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: Optional[dict] = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if not self._devices:
            try:
                # 设置家庭 ID 后重新获取设备列表（带家庭筛选）
                client = self._https_client
                if client and self._selected_family_id:
                    client.family_id = self._selected_family_id
                devices, _, _, rooms, _, _ = await client.fetch_devices()

                # 建立房间名映射
                room_names = {r["roomId"]: r.get("roomName", "") for r in rooms}

                # 过滤 WiFi 设备和隐藏设备，只展示 LAN 可控设备
                from .const import DEVICE_TYPE_MAP, HIDDEN_TYPES
                _LAN_TYPES = set(DEVICE_TYPE_MAP.keys()) - HIDDEN_TYPES

                self._devices = []
                for d in devices:
                    dt = d.get("deviceType", 0)
                    if isinstance(dt, str):
                        try:
                            dt = int(dt)
                        except (ValueError, TypeError):
                            continue
                    if dt not in _LAN_TYPES:
                        continue
                    # 添加房间名
                    room_id = d.get("roomId", "")
                    d["roomName"] = room_names.get(room_id, "")
                    self._devices.append(d)
            except Exception as e:
                _LOGGER.error(f"获取设备列表失败: {e}", exc_info=True)
                errors["base"] = "cannot_connect"

        if not self._devices:
            if not errors:
                errors["base"] = "no_devices"

        if user_input is not None and CONF_SELECTED_DEVICE_IDS in user_input:
            available = {str(dev["deviceId"]) for dev in self._devices}
            requested = {str(device_id) for device_id in user_input[CONF_SELECTED_DEVICE_IDS]}
            intersection = requested & available
            selected_ids = [
                str(dev["deviceId"])
                for dev in self._devices
                if str(dev["deviceId"]) in intersection
            ]
            if not selected_ids:
                errors["base"] = "no_devices_selected"
            else:
                return await self._create_entry(selected_ids)

        return self.async_show_form(
            step_id="devices",
            data_schema=_device_schema(self._devices),
            errors=errors,
        )

    async def _create_entry(self, selected_ids: list[str]) -> FlowResult:
        family_id = self._selected_family_id or (
            self._family_list[0]["familyId"] if self._family_list else None
        )

        await self.async_set_unique_id(self._user_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{self._username} - {self._family_name}",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_FAMILY_ID: family_id,
            },
            options={
                CONF_SELECTED_DEVICE_IDS: selected_ids,
            },
        )
