import logging
import ctypes
import numpy as np

logger = logging.getLogger(__name__)


class HolzworthSynthRaw():
    """Raw driver to communicate with the Holzworth Synthesiser using SCPI commands over
    USB"""
    def __init__(self):

        self.dll = ctypes.WinDLL("HolzworthHS1001.dll")

        self.dll.getAttachedDevices.restype = ctypes.c_char_p

        self.serialnum = self.dll.getAttachedDevices()

        if self.serialnum.decode() == '':
            raise Exception("No devices connected")

        rc = self.dll.openDevice(self.serialnum)
        assert (rc > 0)

        self.dll.usbCommWrite.restype = ctypes.c_char_p

        self.suffix_dict = {'Hz': 0, 'kHz': 3, 'MHz': 6, 'GHz': 9}  # SI suffixes.
        self.exponent_dict = {v: k
                              for k, v in self.suffix_dict.items()
                              }  # swap keys for values

    def get_freq(self, limits=0):
        """Returns the current set frequency of the Holzworth synth when called without
        arguments or limits=0, and returns the maximum and minimum allowed frequency
        when called with limits=1 and limits =-1 respectively"""

        limits_dict = {0: '', 1: ':MAX', -1: ':MIN'}
        command = ctypes.c_char_p((':FREQ' + limits_dict[limits] + '?').encode())

        rx = self.dll.usbCommWrite(self.serialnum, command)

        freq_string = rx.decode()
        assert (freq_string != 'Invalid Command')
        [value, suffix] = freq_string.strip().split()

        try:
            freq = float(value) * (10**self.suffix_dict[suffix])
        except KeyError as e:
            raise Exception('Invalid suffix "' + e.args[0] + '"')
        return round(freq, 3)  # rounding as the synth reads to 3 d.p. precision

    def set_freq(self, freq):
        """Sets the output frequency of the Holzworth synth"""

        if (freq < 1e5) or (freq > 2.048e9):
            raise Exception("Frequency out of range")

        exponent = int(3.0 * np.floor(
            np.log10(freq) / 3.0))  # find nearest SI suffix exponent (i.e. 0,3,6 or 9)

        try:
            # rounding to 3 d.p. as otherwise synth can set to the wrong frequency.
            freq_string = str(round(freq / (10**exponent),
                                    exponent + 3)) + self.exponent_dict[exponent]
        except KeyError as e:
            raise Exception('Invalid exponent"' + e.args[0] + '"')

        command = ctypes.c_char_p((':FREQ:' + freq_string).encode())
        rx = self.dll.usbCommWrite(self.serialnum, command)
        assert (rx.decode() == 'Frequency Set')

    def get_pow(self, limits=0):
        """Returns the current set power of the Holzworth synth when called without
        arguments or limits=0, and returns the maximum and minimum allowed frequency
        when called with limits=1 and limits =-1 respectively"""
        limits_dict = {0: '', 1: ':MAX', -1: ':MIN'}
        command = ctypes.c_char_p((':PWR' + limits_dict[limits] + '?').encode())

        rx = self.dll.usbCommWrite(self.serialnum, command)

        pow_string = rx.decode()
        assert (pow_string != 'Invalid Command')

        power = float(pow_string.strip(' dBm'))
        return round(power, 3)  # rounding as the synth reads to 3 d.p. precision

    def set_pow(self, power):
        """Sets the output power of the Holzworth synth"""

        if (power < -100) or (power > 15):
            raise Exception("Power out of range")

        pow_string = str(round(power, 2))

        command = ctypes.c_char_p((':PWR:' + pow_string + 'dBm').encode())
        rx = self.dll.usbCommWrite(self.serialnum, command)
        assert (rx.decode() == 'Power Set')

    def identity(self):
        """Retrieves the Manufacturer, Device Name, Board Number, Firmware Version,
        Instrument Serial Number"""
        command = ctypes.c_char_p((':IDN?').encode())
        rx = self.dll.usbCommWrite(self.serialnum, command)
        return rx.decode()

    def ping(self):
        """Needed to check connnection is alive"""
        if self.identity() == '':
            raise Exception("No devices connected")
        return True

    def close(self):
        """Closes connection to the Holzworth. Must be called when disconnecting else
        future connections may not work"""
        self.dll.close_all()
        print('Connection to Holzworth synth closed safely')
