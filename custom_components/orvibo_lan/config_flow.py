"""ORVIBO LAN Control 配置流：输入账号→选择家庭→完成。"""

import logging
import re
from typing import Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_FAMILY_ID

_LOGGER = logging.getLogger(__name__)


class OrviboLanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._username: Optional[str] = None
        self._password: Optional[str] = None
        self._family_list: list = []
        self._family_name: str = ""
        self._selected_family_id: Optional[str] = None
        self._user_id: str = ""

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

                        if len(self._family_list) <= 1:
                            return await self._create_entry()
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
                # 更新家庭名称
                for f in self._family_list:
                    if f["familyId"] == family_id:
                        self._family_name = f.get("familyName", "")
                        break
                return await self._create_entry()

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

    async def _create_entry(self) -> FlowResult:
        family_id = self._selected_family_id or (self._family_list[0]["familyId"] if self._family_list else None)

        await self.async_set_unique_id(self._user_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{self._username} - {self._family_name}",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_FAMILY_ID: family_id,
            },
        )
