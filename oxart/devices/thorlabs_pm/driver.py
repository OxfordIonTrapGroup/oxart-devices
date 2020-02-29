from ctypes import (c_bool, c_char_p, c_double, c_int, c_int16, c_uint32,
    byref, create_string_buffer)
import logging

from oxart.devices.thorlabs_pm.wrapper import (TLPM, TLPM_ATTR_SET_VAL,
    TLPM_BUFFER_SIZE, TLPM_POWER_UNIT_WATT, TLPM_POWER_UNIT_DBM)


logger = logging.getLogger(__name__)


def get_device_names():
    driver = TLPM()
    device_count = c_uint32()
    driver.findRsrc(byref(device_count))
    # print("PM devices found: " + str(device_count.value))

    device_names = []
    for i in range(device_count.value):
        buff = create_string_buffer(1024)
        driver.getRsrcName(c_int(i), buff)
        # print("name: " + c_char_p(buff.raw).value)
        device_names.append(c_char_p(buff.raw).value)

    driver.close()
    return device_names


class ThorlabsPM100A:
    def __init__(self, device_name, query_id=True, reset=False):
        self.device_name = device_name
        self.tlpm = TLPM()
        self.tlpm.open(create_string_buffer(device_name), c_bool(query_id),
                       c_bool(reset))

    def close(self):
        self.tlpm.close()

    def set_wavelength(self, wavelength):
        """
        Set wavelength in nanometers to use for measurements.
        """
        self.tlpm.setWavelength(c_double(wavelength))

    def get_wavelength(self):
        """
        Return the wavelength in nanometers currently set for measurements.
        """
        wavelength = c_double()
        self.tlpm.getWavelength(c_int16(TLPM_ATTR_SET_VAL), byref(wavelength))
        return wavelength.value

    def set_power_range(self, pow_range):
        """
        Set the power range for measurements.

        The value passed as pow_range is the maximum power level expected for
        measurements. This is converted to a suitable range by the device
        automatically.
        """
        self.tlpm.setPowerRange(c_double(pow_range))

    def get_power_range(self):
        """
        Return the power range currently set for measurements.
        """
        pow_range = c_double()
        self.tlpm.getPowerRange(c_int16(TLPM_ATTR_SET_VAL), byref(pow_range))
        return pow_range.value

    def set_power_unit(self, unit):
        """
        Set the unit for power measurements.

        :param unit: either "W" or "dBm"
        """
        u = TLPM_POWER_UNIT_WATT if unit == "W" else TLPM_POWER_UNIT_DBM
        self.tlpm.setPowerUnit(c_int16(u))

    def get_latest_reading(self):
        """
        Take a power measurement.

        The unit of the returned value depends on the current setting, which
        can be changed via :meth set_power_unit:.
        """
        power = c_double()
        self.tlpm.measPower(byref(power))
        return power.value

    def set_attenuation_factor(self, att):
        """
        Set the input attenuation factor in dB.

        The attenuation factor describes the attenuation of optical power
        before light reaches the power meter. The value returned by a
        measurement is adjusted to give the power level before attenuation,
        so
            dBm_measurement = dBm_raw + att
        """
        self.tlpm.setAttenuation(c_double(att))

    def get_device_info(self):
        device_count = c_uint32()
        self.tlpm.findRsrc(byref(device_count))

        idx = 0
        for i in range(device_count.value):
            buff = create_string_buffer(1024)
            self.tlpm.getRsrcName(c_int(i), buff)
            name = c_char_p(buff.raw).value
            if name == self.device_name:
                idx = i

        model_name = create_string_buffer(TLPM_BUFFER_SIZE)
        serial_number = create_string_buffer(TLPM_BUFFER_SIZE)
        manufacturer = create_string_buffer(TLPM_BUFFER_SIZE)
        available = create_string_buffer(TLPM_BUFFER_SIZE)
        self.tlpm.getRsrcInfo(idx, model_name, serial_number, manufacturer,
                              available)

        info_dict = {
            "model_name": c_char_p(model_name.raw).value,
            "serial_number": c_char_p(serial_number.raw).value,
            "manufacturer": c_char_p(manufacturer.raw).value,
        }

        return info_dict


