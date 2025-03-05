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
    HVACMode,
)

from .core.aiot_manager import AiotEntityBase
from .core.const import DOMAIN, HASS_DATA_AIOT_MANAGER

from .core.aiot_manager import (
    AiotManager,
    AiotEntityBase,
)

TYPE = "climate"

_LOGGER = logging.getLogger(__name__)

DATA_KEY = f"{TYPE}.{DOMAIN}"



# HA模式到设备模式值的映射
P3_MODE_ATTR_RES_MAPPING = {
    HVACMode.COOL: "0",     # 制冷
    HVACMode.HEAT: "1",     # 制热
    HVACMode.AUTO: "2",     # 自动
    HVACMode.FAN_ONLY: "3", # 送风
    HVACMode.DRY: "4"       # 除湿
}

# 设备模式值到HA模式的映射
P3_MODE_RES_ATTR_MAPPING = {
    "0": HVACMode.COOL,
    "1": HVACMode.HEAT,
    "2": HVACMode.AUTO,
    "3": HVACMode.FAN_ONLY,
    "4": HVACMode.DRY
}

LIGHT_ON = "on"
LIGHT_OFF = "off"

# HA风速到设备风速值的映射
P3_FAN_ATTR_RES_MAPPING = {
    FAN_AUTO: "0",   # 自动
    FAN_LOW: "1",    # 小风量
    FAN_MEDIUM: "2", # 中风量
    FAN_HIGH: "3"    # 大风量
}

# 设备风速值到HA风速的映射
P3_FAN_RES_ATTR_MAPPING = {
    "0": FAN_AUTO,
    "1": FAN_LOW,
    "2": FAN_MEDIUM,
    "3": FAN_HIGH
}


class AiotACPartnerP3Entity(AiotEntityBase, ClimateEntity):
    def __init__(self, hass, device, res_params, channel=None, **kwargs):
        AiotEntityBase.__init__(self, hass, device, res_params, TYPE, channel, **kwargs)
        self._attr_temperature_unit = kwargs.get("temperature_unit")
        self._attr_hvac_modes = kwargs.get("hvac_modes")
        self._attr_fan_modes = kwargs.get("fan_modes")
        self._attr_swing_modes = kwargs.get("swing_modes")
        self._attr_preset_modes = kwargs.get("preset_modes")
        self._attr_target_temperature_step = kwargs.get("target_temperature_step")

        self._attr_max_temp = kwargs.get("max_temp")
        self._attr_min_temp = kwargs.get("min_temp")
        self._attr_target_temperature_high = kwargs.get("max_temp")
        self._attr_target_temperature_low = kwargs.get("min_temp")
        
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_last_hvac_mode = HVACMode.AUTO  # 新增：记录最后一次有效模式
        self._attr_target_temperature = 24
        self._attr_fan_mode = FAN_AUTO
        self._attr_swing_mode = SWING_ON
        self._attr_light_mode = LIGHT_ON
        self._attr_preset_mode = None

    def convert_res_to_attr(self, res_name, res_value):
        if res_name == "ac_fun_ctl":
            self.ac_fun_ctl_to_attr(res_value)
        elif res_name == "ac_quick_cool":
            self.ac_quick_cool_to_attr(res_value)

    def ac_fun_ctl_to_attr(self, value):
        """空调功能控制 P3 转HA属性."""
        _LOGGER.debug(f"Received ac_fun_ctl value: {value}")
        if value:
            pattern = r"^P(\d+)_M(\d+)_T(\d+)_S(\d+)_D(\d+)_L(\d+)$"
            match = re.fullmatch(pattern, value)
            if not match:
                _LOGGER.error(f"Invalid acKey format: {value}")
                return

            power, mode, temp, fan, swing, light = match.groups()

            _LOGGER.debug(f"Parsed values - Power: {power}, Mode: {mode}, Temperature: {temp}, Fan: {fan}, Swing: {swing}, Light: {light}")

            # 更新开关状态
            if power == "1":
                self._attr_hvac_mode = HVACMode.OFF
            else:
                # 更新模式并记录最后一次有效模式
                new_mode = P3_MODE_RES_ATTR_MAPPING.get(mode, HVACMode.AUTO)
                self._attr_hvac_mode = new_mode
                self._attr_last_hvac_mode = new_mode  # 记录最后一次有效模式
            # 更新温度
            self._attr_target_temperature = int(temp)
            # 更新风速
            self._attr_fan_mode = P3_FAN_RES_ATTR_MAPPING.get(fan, FAN_AUTO)
            # 更新扫风
            self._attr_swing_mode = SWING_ON if swing == "0" else SWING_OFF
            # 更新灯光
            self._attr_light_mode = LIGHT_ON if light == "1" else LIGHT_OFF

            _LOGGER.debug(f"Updated attributes: hvac_mode={self._attr_hvac_mode}, target_temperature={self._attr_target_temperature}, fan_mode={self._attr_fan_mode}, swing_mode={self._attr_swing_mode}, light_mode={self._attr_light_mode}")

            self.schedule_update_ha_state()

    def ac_quick_cool_to_attr(self, value):
        try:
            value = int(value)
            if value == 1:
                self._attr_preset_mode = PRESET_BOOST
                _LOGGER.debug("急速模式已激活")
            elif value == 0:
                self._attr_preset_mode = PRESET_NONE
                _LOGGER.debug("急速模式已关闭")
            else:
                _LOGGER.error(f"无效的 ac_quick_cool 值: {value}")
        except ValueError:
            _LOGGER.error(f"ac_quick_cool 值格式错误: {value}")
        self.schedule_update_ha_state()

    def attr_to_ac_fun_ctl(self, attr, value):
        """生成控制指令（如 P0_M4_T19_S1_D1_L0）"""
        # 生成 power 参数
        if attr == "hvac_mode":
            if value == HVACMode.OFF:
                power = 1  # 关机
                self._attr_last_hvac_mode = self._attr_hvac_mode  # 关机前保存当前模式
                mode = "2"  # 设备忽略此值，可设为任意
            else:
                power = 0  # 开机
                mode = P3_MODE_ATTR_RES_MAPPING.get(value, "2")
                self._attr_last_hvac_mode = value  # 更新最后一次有效模式
            self._attr_hvac_mode = value
        else:
            power = 1 if self._attr_hvac_mode == HVACMode.OFF else 0

        # 生成 mode 参数（开机时使用最后一次记录的模式）
        if power == 0 and self._attr_hvac_mode != HVACMode.OFF:
            mode = P3_MODE_ATTR_RES_MAPPING.get(self._attr_hvac_mode, "2")
        else:
            mode = "2"  # 默认值（设备可能忽略）

        # 生成 temp 参数（限制在16~30）
        temp = int(max(16, min(30, self._attr_target_temperature)))

        # 生成 fan 参数
        fan = P3_FAN_RES_ATTR_MAPPING.get(self._attr_fan_mode, "0")

        # 生成 swing 参数
        swing = 0 if self._attr_swing_mode == SWING_ON else 1

        # 生成 light 参数
        light = 1 if self._attr_light_mode == LIGHT_ON else 0

        # 生成指令
        result = f"P{power}_M{mode}_T{temp}_S{fan}_D{swing}_L{light}"
        _LOGGER.debug(f"生成控制指令: {result}")
        return result

    async def async_turn_on(self):
        """覆盖父类方法：开启空调时使用最后一次记录的模式"""
        _LOGGER.debug("Turning on the air conditioner")
        await self.async_set_hvac_mode(self._attr_last_hvac_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        _LOGGER.debug(f"Setting HVAC mode to {hvac_mode}")
        result = self.attr_to_ac_fun_ctl("hvac_mode", hvac_mode)
        await self.async_set_res_value("ac_fun_ctl", result)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        _LOGGER.debug(f"Setting temperature to {temp}")
        result = self.attr_to_ac_fun_ctl("target_temperature", temp)
        await self.async_set_res_value("ac_fun_ctl", result)

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        _LOGGER.debug(f"Setting fan mode to {fan_mode}")
        result = self.attr_to_ac_fun_ctl("fan_mode", fan_mode)
        await self.async_set_res_value("ac_fun_ctl", result)

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        _LOGGER.debug(f"Setting swing mode to {swing_mode}")
        result = self.attr_to_ac_fun_ctl("swing_mode", swing_mode)
        await self.async_set_res_value("ac_fun_ctl", result)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        _LOGGER.debug(f"Setting preset mode to {preset_mode}")
        if preset_mode == PRESET_BOOST:
            await self.async_set_res_value("ac_quick_cool", "1")
        elif preset_mode == PRESET_NONE:
            await self.async_set_res_value("ac_quick_cool", "0")