"""Orvibo LAN Cover 平台（窗帘）。"""

import logging
from collections.abc import Mapping
from typing import Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import OrviboLanCoordinator
from .device_profiles import supports_platform
from .entity import OrviboLanEntity
from .lib import device_control as dc

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # 延迟导入，避免 HA 2026 import_module 阻塞检测
    from homeassistant.components.cover import (
        ATTR_POSITION,
        ATTR_TILT_POSITION,
        CoverDeviceClass,
        CoverEntity,
        CoverEntityFeature,
    )

    class OrviboLanCover(OrviboLanEntity, CoverEntity):
        """Orvibo 窗帘实体。"""

        _attr_has_entity_name = True

        def __init__(self, coordinator, device_id, device, device_type=34):
            super().__init__(coordinator)
            self._device_id = device_id
            self._device = device
            self._device_type = device_type
            name = device.get("deviceName", f"Cover {device_id[:8]}")
            self._attr_unique_id = f"{DOMAIN}_cover_{device_id}"
            self._attr_name = name
            # type=35 卷帘使用 SHUTTER 图标
            if device_type == 35:
                self._attr_device_class = CoverDeviceClass.SHUTTER
                self._attr_icon = "mdi:roller-shade"
            else:
                self._attr_device_class = CoverDeviceClass.CURTAIN

            # 每个设备独立注册为 HA 设备，via_device 指向网关
            uid = device.get("uid", "")
            dev_info = {
                "identifiers": {(DOMAIN, f"device_{device_id}")},
                "name": device.get("deviceName", f"Cover {device_id[:8]}"),
                "manufacturer": MANUFACTURER,
                "model": "Orvibo Curtain",
            }
            if uid and device.get("_orvibo_lan_capable"):
                dev_info["via_device"] = (DOMAIN, f"gateway_{uid}")
            self._attr_device_info = dev_info

        def _curtain_props(self, st: dict) -> Optional[Mapping]:
            """梦幻帘(506)位置/角度在 properties.curtain（value1 固定 -1）。"""
            properties = st.get("properties")
            if not isinstance(properties, Mapping):
                return None
            curtain = properties.get("curtain")
            if not isinstance(curtain, Mapping):
                return None
            return curtain

        def _parse_position(self, st: dict) -> Optional[int]:
            """解析窗帘位置。cmd=42: value1=0关100开，跟 HA 一致，直接返回。
            梦幻帘(506) value1 固定 -1（无效哨兵值），位置在 properties.curtain.percent。"""
            v1 = st.get("value1")
            if v1 is not None:
                pos = int(v1)
                if pos >= 0:
                    return max(0, min(pos, 100))
            curtain = self._curtain_props(st)
            if curtain is not None:
                percent = curtain.get("percent")
                if percent is not None:
                    return max(0, min(int(float(percent)), 100))
            return None

        def _parse_tilt(self, st: dict) -> Optional[int]:
            """梦幻帘(506)叶片角度。云端 angle 为度数(0-180)，换算成 HA 0-100。"""
            curtain = self._curtain_props(st)
            if curtain is None:
                return None
            angle = curtain.get("angle")
            if angle is None:
                return None
            return max(0, min(int(round(float(angle) * 100 / 180)), 100))

        @property
        def current_cover_tilt_position(self) -> Optional[int]:
            if self._device_type != 506:
                return None
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            return self._parse_tilt(st)

        @property
        def supported_features(self):
            feats = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
            feats |= CoverEntityFeature.SET_POSITION
            if self._device_type == 506:
                feats |= CoverEntityFeature.SET_TILT_POSITION
            return feats

        @property
        def is_closed(self) -> Optional[bool]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            pos = self._parse_position(st)
            if pos is not None:
                return pos <= 5
            return None

        @property
        def current_cover_position(self) -> Optional[int]:
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            return self._parse_position(st)

        def _curtain_angle_deg(self) -> Optional[int]:
            """当前叶片角度（度数 0-180）。"""
            st = self.coordinator.get_device_state(self._device_id)
            if not st:
                return None
            curtain = self._curtain_props(st)
            if curtain is None:
                return None
            angle = curtain.get("angle")
            if angle is None:
                return None
            return max(0, min(int(round(float(angle))), 180))

        async def async_open_cover(self, **kwargs):
            if self._device_type == 506:
                payload = dc.cover_curtain_angle_open(
                    self._device_id,
                    self._device.get("uid", ""),
                    self._curtain_angle_deg() or 0,
                    self.coordinator.username,
                )
            else:
                payload = dc.cover_open(
                    self._device_id, self._device.get("uid", ""), self.coordinator.username
                )
            await self.coordinator.async_control_device(self._device_id, payload)

        async def async_close_cover(self, **kwargs):
            if self._device_type == 506:
                payload = dc.cover_curtain_angle_close(
                    self._device_id,
                    self._device.get("uid", ""),
                    self._curtain_angle_deg() or 0,
                    self.coordinator.username,
                )
            else:
                payload = dc.cover_close(
                    self._device_id, self._device.get("uid", ""), self.coordinator.username
                )
            await self.coordinator.async_control_device(self._device_id, payload)

        async def async_stop_cover(self, **kwargs):
            if self._device_type == 506:
                payload = dc.cover_curtain_angle_stop(
                    self._device_id, self._device.get("uid", ""), self.coordinator.username
                )
            else:
                payload = dc.cover_stop(
                    self._device_id, self._device.get("uid", ""), self.coordinator.username
                )
            await self.coordinator.async_control_device(self._device_id, payload)

        async def async_set_cover_position(self, **kwargs):
            position = kwargs[ATTR_POSITION]
            if self._device_type == 506:
                angle = self._curtain_angle_deg() or 0
                payload = dc.cover_curtain_angle_position(
                    self._device_id,
                    self._device.get("uid", ""),
                    position,
                    angle,
                    self.coordinator.username,
                )
            else:
                payload = dc.cover_position(
                    self._device_id, self._device.get("uid", ""), position, self.coordinator.username
                )
            await self.coordinator.async_control_device(self._device_id, payload)

        async def async_set_cover_tilt_position(self, **kwargs):
            angle_ha = kwargs[ATTR_TILT_POSITION]
            angle_deg = int(round(int(angle_ha) * 180 / 100))
            pos = self._parse_position(self.coordinator.get_device_state(self._device_id)) or 100
            payload = dc.cover_curtain_angle_tilt(
                self._device_id,
                self._device.get("uid", ""),
                angle_deg,
                pos,
                self.coordinator.username,
            )
            await self.coordinator.async_control_device(self._device_id, payload)

    from . import get_runtime_data

    coordinator: OrviboLanCoordinator = get_runtime_data(hass, entry).coordinator
    from .selection import selected_device_ids

    selected_ids = selected_device_ids(entry.options, coordinator.devices)
    entities = []

    from .const import HIDDEN_TYPES

    for did, device in coordinator.devices.items():
        if did not in selected_ids:
            continue
        dt = coordinator.device_types.get(did, 0)
        if not supports_platform(
            device,
            coordinator.get_device_state(did),
            "cover",
        ):
            continue
        if dt in HIDDEN_TYPES:
            continue

        entities.append(OrviboLanCover(coordinator, did, device, dt))

    if entities:
        async_add_entities(entities)
