import logging
import re
from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_BOOST,
    PRESET_NONE,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)


from .core.aiot_manager import (
    AiotManager,
    AiotEntityBase,
)

from .core.const import DOMAIN, HASS_DATA_AIOT_MANAGER

TYPE = "climate"

_LOGGER = logging.getLogger(__name__)

DATA_KEY = f"{TYPE}.{DOMAIN}"

AC_STATE_RES_ATTR_MAPPING = {
    "hvac_mode": {
        "0": HVACMode.HEAT,
        "1": HVACMode.COOL,
        "2": HVACMode.AUTO,
        "3": HVACMode.DRY,
        "4": HVACMode.FAN_ONLY,
    },
    "fan_mode": {"0": FAN_LOW, "1": FAN_MEDIUM, "2": FAN_HIGH, "3": FAN_AUTO},
    "swing_mode": {"0": SWING_ON, "1": SWING_OFF},
}

AC_STATE_ATTR_RES_MAPPING = {
    "hvac_mode": {
        HVACMode.HEAT: "0",
        HVACMode.COOL: "1",
        HVACMode.AUTO: "2",
        HVACMode.DRY: "3",
        HVACMode.FAN_ONLY: "4",
    },
    "fan_mode": {
        FAN_LOW: "0",
        FAN_MEDIUM: "1",
        FAN_HIGH: "2",
        FAN_AUTO: "3",
    },
    "swing_mode": {SWING_ON: "0", SWING_OFF: "1"},
}


P3_MODE_RES_ATTR_MAPPING = {
    "0": HVACMode.COOL,
    "1": HVACMode.HEAT,
    "2": HVACMode.AUTO,
    "3": HVACMode.FAN_ONLY,
    "4": HVACMode.DRY,
}

P3_MODE_ATTR_RES_MAPPING = {
    HVACMode.COOL: "0",
    HVACMode.HEAT: "1",
    HVACMode.AUTO: "2",
    HVACMode.FAN_ONLY: "3",
    HVACMode.DRY: "4",
}

P3_FAN_RES_ATTR_MAPPING = {
    "0": FAN_AUTO,
    "1": FAN_LOW,
    "2": FAN_MEDIUM,
    "3": FAN_HIGH,
}

P3_FAN_ATTR_RES_MAPPING = {
    FAN_AUTO: "0",
    FAN_LOW: "1",
    FAN_MEDIUM: "2",
    FAN_HIGH: "3",
}

class AiotACPartnerP3Entity(AiotEntityBase, ClimateEntity):
    def __init__(self, hass, device, res_params, channel=None, **kwargs):
        AiotEntityBase.__init__(self, hass, device, res_params, TYPE, channel, **kwargs)
        self._attr_temperature_unit = kwargs.get("temperature_unit")
        self._attr_hvac_modes = kwargs.get("hvac_modes", [HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY])
        self._attr_fan_modes = kwargs.get("fan_modes", [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH])
        self._attr_swing_modes = kwargs.get("swing_modes", [SWING_OFF, SWING_ON])
        self._attr_preset_modes = kwargs.get("preset_modes", [PRESET_NONE, PRESET_BOOST])
        self._attr_target_temperature_step = kwargs.get("target_temperature_step", 0.5)  # Initialize to 0.5 degrees

        self._attr_max_temp = kwargs.get("max_temp", 30)
        self._attr_min_temp = kwargs.get("min_temp", 16)
        self._attr_target_temperature_high = kwargs.get("max_temp", 30)
        self._attr_target_temperature_low = kwargs.get("min_temp", 16)
        
        self._attr_target_temperature = kwargs.get("target_temperature", 22)
        self._attr_preset_mode = None
        self._attr_hvac_mode = HVACMode.OFF 
        self._attr_fan_mode = FAN_AUTO 
        self._attr_swing_mode = SWING_OFF 

        
    def convert_res_to_attr(self, res_name, res_value):
        if res_name == "ac_fun_ctl":
            self.ac_fun_ctl_to_attr(res_value)
        elif res_name == "ac_quick_cool":
            self.ac_quick_cool_to_attr(res_value)

    def ac_fun_ctl_to_attr(self, value):
        """空调功能控制 8.0.2116(P3) 转HA属性."""
        if value:
            # 用于处理ac_fun_ctl内容
            pattern = r"^P(\d+)_M(\d+)_T(\d+)_S(\d+)_D(\d+)(?:_L(\d+))?$"
            match = re.fullmatch(pattern, value)
            if not match:
                _LOGGER.error(f"Invalid 8.0.2116(P3) format.")
                return
            # 提取参数（注意group6可能为None）
            power = int(match.group(1))  # P值
            mode = int(match.group(2))  # M值
            temp = int(match.group(3))  # T值
            fan = int(match.group(4))  # S值
            swing = int(match.group(5))  # D值
            light = match.group(6)  # L值（可能为None）
            light = int(light) if light is not None else None

            if power == 0:
                self._attr_hvac_mode = HVACMode.OFF
            elif power == 1:
                self._attr_hvac_mode = P3_MODE_RES_ATTR_MAPPING.get(
                    str(mode), HVACMode.AUTO
                )

            if temp:
                self._attr_target_temperature = float(temp)

            self._attr_fan_mode = P3_FAN_RES_ATTR_MAPPING.get(str(fan), FAN_AUTO)

            if swing == 0:
                self._attr_swing_mode = SWING_ON
                
            else:
                self._attr_swing_mode = SWING_OFF

            self.schedule_update_ha_state()

    def ac_quick_cool_to_attr(self, value):
        value = int(value)
        if value == 1:
            self._attr_preset_mode = PRESET_BOOST
        elif value == 0:
            self._attr_preset_mode = PRESET_NONE

        self.schedule_update_ha_state()

    def attr_to_ac_fun_ctl(self, attr, value):
        """HA属性 转 空调功能控制 8.0.2116(P3)."""

        power = 1 if self._attr_hvac_mode == HVACMode.OFF else 0

        mode = P3_MODE_ATTR_RES_MAPPING.get(self._attr_hvac_mode, "0")

        temp = str(int(self._attr_target_temperature))

        fan = P3_FAN_ATTR_RES_MAPPING.get(self._attr_fan_mode, "2")

        swing = 0 if self._attr_swing_mode == SWING_ON else 1
        
        light = None
        
        if attr == "hvac_mode":
            old_mode = self._attr_hvac_mode
            if value == HVACMode.OFF:
                power = 1
                mode = P3_MODE_ATTR_RES_MAPPING.get(old_mode, HVACMode.AUTO)
            else:
                power = 0
                mode = P3_MODE_ATTR_RES_MAPPING.get(value, HVACMode.AUTO)
            self._attr_hvac_mode = value

        if attr == "target_temperature":
            self._attr_target_temperature = value
            temp = int(value)

        if attr == "fan_mode":
            self._attr_fan_mode = value
            fan = P3_FAN_ATTR_RES_MAPPING.get(value, FAN_AUTO)

        if attr == "swing_mode":
            self._attr_swing_mode = value
            swing = 0 if value == SWING_ON else 1

        self.schedule_update_ha_state()

        result = f"P{power}_M{mode}_T{temp}_S{fan}_D{swing}"
        # _LOGGER.info(f"ac_fun_ctl: {result}")
        return result


    async def async_set_hvac_mode(self, hvac_mode):
        _LOGGER.debug(f"Setting HVAC mode to {hvac_mode}")
        try:
            # 确保 hvac_mode 的值在有效范围内
            if hvac_mode not in [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.OFF]:
                _LOGGER.error(f"Invalid HVAC mode: {hvac_mode}")
                return
            command = self.attr_to_ac_fun_ctl("hvac_mode", hvac_mode)
            _LOGGER.debug(f"Command to send: {command}")
            await self.async_set_res_value("ac_fun_ctl", command)
        except Exception as e:
            _LOGGER.error(f"Failed to set HVAC mode: {e}")

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        _LOGGER.debug(f"Setting temperature to {temp}")
        try:
            if temp < self._attr_min_temp or temp > self._attr_max_temp:
                _LOGGER.error(f"Invalid temperature: {temp}")
                return
            command = self.attr_to_ac_fun_ctl("target_temperature", temp)
            _LOGGER.debug(f"Command to send: {command}")
            await self.async_set_res_value("ac_fun_ctl", command)
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature: {e}")

    async def async_set_fan_mode(self, fan_mode):
        _LOGGER.debug(f"Setting fan mode to {fan_mode}")
        try:
            if fan_mode not in [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]:
                _LOGGER.error(f"Invalid fan mode: {fan_mode}")
                return
            command = self.attr_to_ac_fun_ctl("fan_mode", fan_mode)
            _LOGGER.debug(f"Command to send: {command}")
            await self.async_set_res_value("ac_fun_ctl", command)
        except Exception as e:
            _LOGGER.error(f"Failed to set fan mode: {e}")

    async def async_set_swing_mode(self, swing_mode):
        _LOGGER.debug(f"Setting swing mode to {swing_mode}")
        try:
            if swing_mode not in [SWING_ON, SWING_OFF]:
                _LOGGER.error(f"Invalid swing mode: {swing_mode}")
                return
            command = self.attr_to_ac_fun_ctl("swing_mode", swing_mode)
            _LOGGER.debug(f"Command to send: {command}")
            await self.async_set_res_value("ac_fun_ctl", command)
        except Exception as e:
            _LOGGER.error(f"Failed to set swing mode: {e}")

    async def async_set_preset_mode(self, preset_mode):
        _LOGGER.debug(f"Setting preset mode to {preset_mode}")
        try:
            if preset_mode not in [PRESET_NONE, PRESET_BOOST]:
                _LOGGER.error(f"Invalid preset mode: {preset_mode}")
                return
            command = "1" if preset_mode == PRESET_BOOST else "0"
            _LOGGER.debug(f"Command to send: {command}")
            await self.async_set_res_value("ac_quick_cool", command)
        except Exception as e:
            _LOGGER.error(f"Failed to set preset mode: {e}")
