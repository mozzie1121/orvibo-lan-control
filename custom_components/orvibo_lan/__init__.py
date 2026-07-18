"""ORVIBO LAN Control - 纯局域网控制的 HomeAssistant 集成。"""

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_FAMILY_ID, PLATFORMS
from .coordinator import OrviboLanCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """设置集成入口。"""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    family_id = entry.data.get(CONF_FAMILY_ID)

    coordinator = OrviboLanCoordinator(hass, username, password, family_id)

    try:
        await coordinator._async_setup()
    except Exception as e:
        _LOGGER.error(f"Coordinator 设置失败: {e}", exc_info=True)
        raise ConfigEntryNotReady from e

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Orvibo LAN Control 设置完成")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """卸载集成。"""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_cleanup()

    # HA 2026 要求逐个 domain 卸载
    unload_ok = True
    for domain in PLATFORMS:
        result = await hass.config_entries.async_forward_entry_unload(entry, domain)
        if not result:
            unload_ok = False

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
