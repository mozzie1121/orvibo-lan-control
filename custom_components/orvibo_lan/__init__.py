"""ORVIBO LAN Control - 纯局域网控制的 HomeAssistant 集成。"""

import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STARTED
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_FAMILY_ID, PLATFORMS, MANUFACTURER
from .coordinator import OrviboLanCoordinator

_LOGGER = logging.getLogger(__name__)


async def _async_assign_areas(hass: HomeAssistant, entry: ConfigEntry):
    """在 HA 启动完成后，将设备分配到对应的区域（房间）。"""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        return

    from homeassistant.helpers import device_registry as dr, area_registry as ar
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    # 分配区域
    for did, device in coordinator.devices.items():
        dt = coordinator.device_types.get(did, 0)
        if dt == 114:
            continue
        # 跳过无法本地控制的设备
        if device.get("model", "") == "d4c7d528472e46edb694289300fa6fbb":
            continue
        room_name = coordinator.get_room_name(did)
        if not room_name:
            continue

        area = area_reg.async_get_area_by_name(room_name)
        if not area:
            area = area_reg.async_create(room_name)

        device_entry = dev_reg.async_get_device(
            identifiers={(DOMAIN, f"device_{did}")}
        )

        if device_entry and device_entry.area_id != area.id:
            dev_reg.async_update_device(device_entry.id, area_id=area.id)
            _LOGGER.debug(f"设备 {device.get('deviceName', did)} → 区域 {room_name}")
        elif not device_entry:
            _LOGGER.debug(f"设备 {device.get('deviceName', did)} 未注册到 device registry，跳过区域分配")


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

    from homeassistant.helpers import device_registry as dr
    dev_reg = dr.async_get(hass)
    _LOGGER.debug(f"[注册网关] gateway_ips keys: {list(coordinator._gateway_ips.keys())}")
    for uid, ip in coordinator._gateway_ips.items():
        _LOGGER.debug(f"[注册网关] 注册 gateway_{uid}")
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, f"gateway_{uid}")},
            manufacturer=MANUFACTURER,
            name="Orvibo Gateway",
            model="MixPad",
            sw_version="1.0",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if hass.is_running:
        await _async_assign_areas(hass, entry)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED,
                                   lambda _: hass.create_task(_async_assign_areas(hass, entry)))

    _LOGGER.debug("Orvibo LAN Control 设置完成")
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
