"""Module for instance of a Vaunix LabBrick Signal Generator
"""

from ctypes import *
from os.path import dirname, join
import socket

hostname = socket.getfqdn()
dll_path = join(dirname(__file__), r"vnx_fsynth.dll")
kHz = 1e3

vnx = CDLL(dll_path)
vnx.fnLSG_SetTestMode(False)  # Use actual devices
DeviceIDArray = c_int * 20
Devices = DeviceIDArray()  # This array will hold the list of device handles
# returned by the DLL

# GetNumDevices will determine how many LSG devices are availible
numDevices = vnx.fnLSG_GetNumDevices()

# GetDevInfo generates a list, stored in the devices array, of
# every availible LSG device attached to the system
dev_info = vnx.fnLSG_GetDevInfo(Devices)


def get_device(serial_number):
    for i in range(numDevices):
        dev = Devices[i]
        device_serial_number = vnx.fnLSG_GetSerialNumber(dev)
        if serial_number == device_serial_number:
            return dev

    print(
        str(numDevices),
        " device(s) found on computer ",
        socket.gethostbyname_ex(hostname)[-1],
    )
    # GetSerialNumber will return the devices serial number
    for i in range(numDevices):
        ser_num = vnx.fnLSG_GetSerialNumber(Devices[i])
        print("Serial number of device %d:" % i, str(ser_num))

    raise (RuntimeError("Device with serial number %d could not be found" %
                        serial_number))


class VaunixSG(object):

    def __init__(self, serial_number):
        # serial_number is an integer which should be written under the device
        # alternatively, one can run this driver file which should print the
        # serial numbers of every device currently connected (and not operated
        # through a GUI)

        self.dev = get_device(serial_number)

        # InitDevice wil prepare the device for operation
        vnx.fnLSG_InitDevice(self.dev)

        # These functions will get the frequency range of the LSG device
        # by default, these are expressed in 100kHz units
        self.min_freq_100kHz = vnx.fnLSG_GetMinFreq(self.dev)
        self.max_freq_100kHz = vnx.fnLSG_GetMaxFreq(self.dev)
        self.min_freq_Hz = self.min_freq_100kHz * 100 * kHz
        self.max_freq_Hz = self.max_freq_100kHz * 100 * kHz

        # These functions get the minimum and maximum power of the LSG device
        # The powerlevel is encoded as the number of .25dB increments, with a
        # resolution of .5dB. To set a power level of +5 dBm, for example, powerlevel
        # would be 20. To set a
        # power level of -20 dBm, powerlevel would be -80.
        self.min_power_025dBm = vnx.fnLSG_GetMinPwr(self.dev)
        self.max_power_025dBm = vnx.fnLSG_GetMaxPwr(self.dev)
        self.min_power_dBm = self.min_power_025dBm / 4
        self.max_power_dBm = self.max_power_025dBm / 4

    def ping(self):
        result = vnx.fnLSG_GetDeviceStatus(self.dev)
        if int(result) == 16456:
            # device is disconnected
            return False
        return True

    def set_on(self, on):
        """This function turns the RF stages of the synthesizer on (on = True) or off
        (on = False)."""
        vnx.fnLSG_SetRFOn(self.dev, on)

    def get_on(self):
        """This function returns a bool value which is True when the synthesizer is
        “on”, or False when the
        synthesizer has been set “off”."""
        on = vnx.fnLSG_GetRF_On(self.dev)
        if int(on) == 1:
            return True
        else:
            return False

    def set_ref_internal(self, internal):
        """This function configures the synthesizer to use the internal reference
        if internal = True. If internal = False, then the synthesizer is configured
        to use an external frequency reference.

        22/09/2025: it seems we need to flip logical value here to get
        correct result (see caqtus notes)
        """
        vnx.fnLSG_SetUseInternalRef(self.dev, not (internal))

    def get_ref_internal(self):
        """This function returns a bool value which is True when the synthesizer is
        configured to use its internal frequency reference. It returns a value of False
        when the synthesizer is configured to use an external frequency reference."""
        internal = vnx.fnLSG_GetUseInternalRef(self.dev)
        if int(internal) == 1:
            return False
        else:
            return True

    def save_settings(self):
        """The LabBrick synthesizers can save their settings, and then resume operating
        with the saved settings when they are powered up. Set the desired parameters,
        then use this function to save the settings."""
        vnx.fnLSG_SaveSettings(self.dev)

    def set_frequency(self, freq):
        """Sets frequency, rounded to nearest multiple of 100 kHz"""

        # convert frequency to integer number of 100kHz units:
        freq_100kHz = round(freq / (100 * kHz))

        if freq_100kHz > self.max_freq_100kHz or freq_100kHz < self.min_freq_100kHz:
            raise ValueError(
                "Frequency (rounded to nearest multiple of 100kHz) out of range")

        result = vnx.fnLSG_SetFrequency(self.dev, int(freq_100kHz))
        if result != 0:
            raise RuntimeError("SetFrequency returned error", result)

    def set_power(self, pow):
        """Sets frequency, rounded to nearest multiple of 0.5 dBm"""

        # convert frequency to integer number of 0.5 dBm units:
        pow_05dBm = round(pow * 2)
        pow_dBm = pow_05dBm / 2  # actual power to be set

        if pow_dBm > self.max_power_dBm or pow_dBm < self.min_power_dBm:
            raise ValueError(
                "Power (rounded to nearest multiple of 0.5dBm) out of range")

        # And then the power is set as an integer number of 0.25 dBm units
        pow_025dBm = pow_05dBm * 2
        result = vnx.fnLSG_SetPowerLevel(self.dev, int(pow_025dBm))
        if result != 0:
            print("SetPowerLevel returned error", result)

    def get_frequency(self):
        """Gets the frequency in Hertz"""
        result = vnx.fnLSG_GetFrequency(self.dev)  # returns a multiple of 100 kHz
        freq_Hz = result * 100 * kHz
        return freq_Hz

    def get_power(self):
        """Gets the power in dBm"""
        result = vnx.fnLSG_GetPowerLevel(self.dev)  # returns as a multiple of 0.25dBm
        power_dBm = (self.max_power_025dBm - result) / 4
        return power_dBm

    def close(self):
        # This function closes the device
        # You should always close the devie when finished with it
        closedev = vnx.fnLSG_CloseDevice(self.dev)
        if closedev != 0:
            raise RuntimeError("CloseDevice returned an error", closedev)


if __name__ == "__main__":
    print(str(numDevices), " device(s) found")
    # GetSerialNumber will return the devices serial number
    for i in range(numDevices):
        ser_num = vnx.fnLSG_GetSerialNumber(Devices[i])
        print("Serial number of device %d:" % i, str(ser_num))

    ser_number_comet_EOM = 13469
    dev = VaunixSG(13469)
    print("pinging...")
    print(dev.ping())
    print("done")

    dev.set_on(True)
    dev.set_ref_internal(True)
    dev.set_frequency(2652300000.0)
    dev.set_power(2.5)
    dev.save_settings()

    print("Output on?", dev.get_on())
    print("Internal ref?", dev.get_ref_internal())
    print("Output frequency for the LSG device:", dev.get_frequency())
    print("Power level for LSG device:", dev.get_power())
    dev.close()
