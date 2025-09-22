from ctypes import (c_bool, c_char_p, c_double, c_int, c_int16, c_long, c_uint32,
                    c_voidp, byref, cdll, create_string_buffer, sizeof)
import logging

# The following constants are taken from the TLPM.h header file in the
# directory of the driver files provided by Thorlabs (usually installed into
# C:/Program Files/...)
# Any changes in that file would need to be reflected here
TLPM_ATTR_SET_VAL = 0
TLPM_ATTR_MIN_VAL = 1
TLPM_ATTR_MAX_VAL = 2
TLPM_ATTR_DFLT_VAL = 3
TLPM_ATTR_AUTO_VAL = 9

TLPM_BUFFER_SIZE = 256
TLPM_ERR_DESCR_BUFFER_SIZE = 512

TLPM_POWER_UNIT_WATT = 0
TLPM_POWER_UNIT_DBM = 1

logger = logging.getLogger(__name__)


def get_device_names():
    """
    Return a list of all Thorlabs power meters connected to this PC.
    """
    driver = _TLPM()
    device_count = driver.find_devices()
    # print("Thorlabs power meter devices found: {}".format(device_count))

    device_names = []
    for i in range(device_count):
        name = driver.fetch_device_name(i)
        # print("name: {}".format(name))
        device_names.append(name)

    driver.close()
    return device_names


class _TLPM:
    def __init__(self):
        if sizeof(c_voidp) == 4:
            self.dll = cdll.LoadLibrary(
                "C:/Program Files/IVI Foundation/VISA/Win64/Bin/TLPM_32.dll")
        else:
            self.dll = cdll.LoadLibrary(
                "C:/Program Files/IVI Foundation/VISA/Win64/Bin/TLPM_64.dll")

        self.dev_session = c_long()
        self.dev_session.value = 0

    def _testForError(self, status):
        if status < 0:
            self._throwError(status)
        return status

    def _throwError(self, code):
        msg = create_string_buffer(1024)
        self.dll.TLPM_errorMessage(self.dev_session, c_int(code), msg)
        raise NameError(c_char_p(msg.raw).value)

    def open(self, device_name, query_id, reset_device):
        """
        Open a connection to a device compatible with this driver.

        This function initializes the instrument driver session and performs
        the following initialization actions:

        (1) Opens a session to the Default Resource Manager resource and a
            session to the specified device using the device name.

        (2) May perform an identification query on the instrument.

        (3) May reset the instrument to a known state.

        (4) Sends initialization commands to the instrument.

        (5) Returns an instrument handle which is used to distinguish between
            different sessions of this instrument driver.

        Each time this function is invoked a unique session is opened.

        Args:
            device_name: Normal string or byte string with the name of the
                device to connect to.

            query_id (bool): Specifies whether an identification query is
                performed during the initialization process.

            reset_device (bool): Specifies whether the instrument is reset
                during the initialization process.
        """
        self.dll.TLPM_close(self.dev_session)
        self.dev_session.value = 0
        # Need to convert to byte string, if it is not one already
        if hasattr(device_name, "encode"):
            device_name = device_name.encode()

        pInvokeResult = self.dll.TLPM_init(create_string_buffer(device_name),
                                           c_bool(query_id), c_bool(reset_device),
                                           byref(self.dev_session))
        self._testForError(pInvokeResult)

    def close(self):
        """
        Close the instrument driver session.

        Note: The instrument must be reinitialized to use it again.
        """
        self.dll.TLPM_close(self.dev_session)

    def find_devices(self):
        """
        Find all driver-compatible devices attached to the PC and return
        number of devices found.

        The function additionally stores information like system name about
        the found resources internally. This information can be retrieved with
        further functions from the class, e.g. :meth fetch_info:.

        Returns:
            device_count.value: The number of connected devices that are
                supported by this driver.
        """
        device_count = c_uint32()
        pInvokeResult = self.dll.TLPM_findRsrc(self.dev_session, byref(device_count))
        self._testForError(pInvokeResult)
        return device_count.value

    def fetch_device_name(self, index):
        """
        This function gets the resource name string needed to open a device
        with :meth open:.

        Note: The data provided by this function was updated at the last call
              of <Find Resources>.

        Args:
            index: This parameter accepts the index of the device to
                get the resource descriptor from.
                Note: The index is zero based. The maximum index to be used
                      here is one less than the number of devices found by the
                      last call of <Find Resources>.

        Returns:
            name of device at given index
        """
        buff = create_string_buffer(1024)
        pInvokeResult = self.dll.TLPM_getRsrcName(self.dev_session, c_int(index), buff)
        self._testForError(pInvokeResult)
        return c_char_p(buff.raw).value.decode()

    def fetch_device_info(self, index):
        """
        This function gets information about a device compatible with this
        driver that is connected to the PC.

        Note: The data provided by this function was updated at the last call
              of <Find Resources>.

        Args:
            index(c_int): This parameter accepts the index of the device to
                get the resource descriptor from.
                The index is zero based. The maximum index to be used here is
                one less than the number of devices found by the last call of
                <Find Resources>.


                Serial interfaces over Bluetooth will return the interface
                name instead of the device model name.

                The serial number is not available for serial interfaces over
                Bluetooth.


                The manufacturer name is not available for serial interfaces
                over Bluetooth.


        Returns:
            info_dict: Dictionary containing information about device
        """
        model_name = create_string_buffer(TLPM_BUFFER_SIZE)
        serial_number = create_string_buffer(TLPM_BUFFER_SIZE)
        manufacturer = create_string_buffer(TLPM_BUFFER_SIZE)
        available = c_int16()

        pInvokeResult = self.dll.TLPM_getRsrcInfo(self.dev_session, c_int(index),
                                                  model_name, serial_number,
                                                  manufacturer, byref(available))
        self._testForError(pInvokeResult)

        info_dict = {
            "model_name": c_char_p(model_name.raw).value.decode(),
            "serial_number": c_char_p(serial_number.raw).value.decode(),
            "manufacturer": c_char_p(manufacturer.raw).value.decode(),
            "available": available.value
        }

        return info_dict

    def reset(self):
        """
        Reset the device connected to in this session.
        """
        pInvokeResult = self.dll.TLPM_reset(self.dev_session)
        self._testForError(pInvokeResult)

    def self_test(self, selfTestResult, description):
        """
        This function runs the device self test routine and returns the test
        result.

        Args:
            selfTestResult(c_int16 use with byref): This parameter contains
                the value returned from the device self test routine. A
                returned zero value indicates a successful run, a value other
                than zero indicates failure.

            description(create_string_buffer): This parameter returns the
                interpreted code as a user-readable message string. The array
                must contain at least 256 elements ViChar[256].

        Returns:
            int: The return value, 0 is for success
        """
        pInvokeResult = self.dll.TLPM_selfTest(self.dev_session, selfTestResult,
                                               description)
        self._testForError(pInvokeResult)
        return pInvokeResult

    def query_revision(self, instrumentDriverRevision, firmwareRevision):
        """
        This function returns the revision numbers of the instrument driver
        and the device firmware.

        Args:
            instrumentDriverRevision(create_string_buffer): This parameter
                returns the Instrument Driver revision. The array must contain
                at least 256 elements ViChar[256].
                You may pass VI_NULL if you do not need this value.


            firmwareRevision(create_string_buffer): This parameter returns the
                device firmware revision. The array must contain at least
                256 elements ViChar[256].
                You may pass VI_NULL if you do not need this value.

        Returns:
            int: The return value, 0 is for success
        """
        pInvokeResult = self.dll.TLPM_revisionQuery(self.dev_session,
                                                    instrumentDriverRevision,
                                                    firmwareRevision)
        self._testForError(pInvokeResult)
        return pInvokeResult

    def query_id(self, manufacturerName, deviceName, serialNumber, firmwareRevision):
        """
        This function returns the device identification information.

        Args:
            manufacturerName(create_string_buffer): This parameter returns the
                manufacturer name. The array must contain at least 256
                elements ViChar[256].
                You may pass VI_NULL if you do not need this value.

            deviceName(create_string_buffer): This parameter returns the
                device name. The array must contain at least 256 elements
                ViChar[256].
                You may pass VI_NULL if you do not need this value.

            serialNumber(create_string_buffer): This parameter returns the
                device serial number. The array must contain at least 256
                elements ViChar[256].
                You may pass VI_NULL if you do not need this value.

            firmwareRevision(create_string_buffer): This parameter returns the
                device firmware revision. The array must contain at least 256
                elements ViChar[256].
                You may pass VI_NULL if you do not need this value.

        Returns:
            int: The return value, 0 is for success
        """
        pInvokeResult = self.dll.TLPM_identificationQuery(self.dev_session,
                                                          manufacturerName, deviceName,
                                                          serialNumber,
                                                          firmwareRevision)
        self._testForError(pInvokeResult)
        return pInvokeResult


class ThorlabsPM100A(_TLPM):
    def __init__(self, device_name, query_device=True, reset_device=False):
        self.device_name = device_name
        super().__init__()
        self.open(device_name, query_device, reset_device)

    def set_wavelength(self, wavelength):
        """
        Set wavelength in nanometers to use for measurements.
        """
        pInvokeResult = self.dll.TLPM_setWavelength(self.dev_session,
                                                    c_double(wavelength))
        self._testForError(pInvokeResult)

    def get_wavelength(self):
        """
        Return the wavelength in nanometers currently set for measurements.
        """
        wavelength = c_double()
        pInvokeResult = self.dll.TLPM_getWavelength(self.dev_session,
                                                    c_int16(TLPM_ATTR_SET_VAL),
                                                    byref(wavelength))
        self._testForError(pInvokeResult)
        return wavelength.value

    def set_power_range(self, power):
        """
        Set the power range for measurements.

        :param power: maximum power level expected for measurements in
            Watts. This is converted to a suitable range by the device
            automatically.
        """
        pInvokeResult = self.dll.TLPM_setPowerRange(self.dev_session, c_double(power))
        self._testForError(pInvokeResult)

    def get_power_range(self):
        """
        Return the power range currently set for measurements.
        """
        pow_range = c_double()
        pInvokeResult = self.dll.TLPM_getPowerRange(self.dev_session,
                                                    c_int16(TLPM_ATTR_SET_VAL),
                                                    byref(pow_range))
        self._testForError(pInvokeResult)
        return pow_range.value

    def set_power_unit(self, unit):
        """
        Set the unit for power measurements.

        :param unit: either "W" or "dBm"
        """
        u = TLPM_POWER_UNIT_WATT if unit == "W" else TLPM_POWER_UNIT_DBM

        pInvokeResult = self.dll.TLPM_setPowerUnit(self.dev_session, c_int16(u))
        self._testForError(pInvokeResult)

    def get_power_reading(self):
        """
        Take a power measurement.

        The unit of the returned value depends on the current setting of the
        power unit, which can be changed via :meth set_power_unit:.
        """
        power = c_double()
        pInvokeResult = self.dll.TLPM_measPower(self.dev_session, byref(power))
        self._testForError(pInvokeResult)
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
        pInvokeResult = self.dll.TLPM_setAttenuation(self.dev_session, c_double(att))
        self._testForError(pInvokeResult)

    def get_device_info(self):
        device_count = self.find_devices()
        idx = -1
        for i in range(device_count):
            name = self.fetch_device_name(i)
            if name == self.device_name:
                idx = i

        if idx == -1:
            return None
        else:
            info_dict = self.fetch_device_info(idx)
            # Driver is connected to this device, so it is never available
            del info_dict["available"]
            return info_dict

    def ping(self):
        return True
