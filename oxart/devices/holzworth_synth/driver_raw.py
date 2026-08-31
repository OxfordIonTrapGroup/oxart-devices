import ctypes
import logging
import math

logger = logging.getLogger(__name__)


class HolzworthSynthRaw:
    """Raw driver to communicate with the Holzworth Synthesiser using SCPI commands
    over USB."""

    # SI suffixes accepted/returned by the synth, and their decimal exponents.
    suffix_exponents = {"Hz": 0, "kHz": 3, "MHz": 6, "GHz": 9}
    exponent_suffixes = {v: k for k, v in suffix_exponents.items()}

    min_freq = 1e5
    max_freq = 2.048e9
    min_pow = -100.
    max_pow = 15.

    def __init__(self):
        self.dll = ctypes.WinDLL("HolzworthHS1001.dll")

        self.dll.getAttachedDevices.restype = ctypes.c_char_p
        self.dll.usbCommWrite.restype = ctypes.c_char_p

        self.serialnum = self.dll.getAttachedDevices()
        if not self.serialnum or not self.serialnum.decode():
            raise RuntimeError("No devices connected")

        rc = self.dll.openDevice(self.serialnum)
        if rc <= 0:
            raise RuntimeError("Could not open device '{}' (error code {})".format(
                self.serialnum.decode(), rc))

        self._closed = False

    def _query(self, command):
        """Send an SCPI command to the synth and return its (stripped) response."""
        rx = self.dll.usbCommWrite(self.serialnum, ctypes.c_char_p(command.encode()))
        if rx is None:
            raise RuntimeError("No response to command '{}'".format(command))
        response = rx.decode().strip()
        if response == "Invalid Command":
            raise RuntimeError("Synth rejected command '{}'".format(command))
        return response

    def get_freq(self, limits=0):
        """Returns the current set frequency of the Holzworth synth when called
        without arguments or limits=0, and returns the maximum and minimum allowed
        frequency when called with limits=1 and limits =-1 respectively."""

        limits_dict = {0: '', 1: ':MAX', -1: ':MIN'}
        freq_string = self._query(':FREQ' + limits_dict[limits] + '?')

        [value, suffix] = freq_string.split()
        try:
            freq = float(value) * (10**self.suffix_exponents[suffix])
        except KeyError as e:
            raise RuntimeError('Invalid suffix "' + e.args[0] + '"') from e
        return round(freq, 3)  # rounding as the synth reads to 3 d.p. precision

    def set_freq(self, freq):
        """Sets the output frequency of the Holzworth synth."""

        if (freq < self.min_freq) or (freq > self.max_freq):
            raise ValueError("Frequency {} Hz out of range ({} to {} Hz)".format(
                freq, self.min_freq, self.max_freq))

        # Find the nearest SI suffix exponent (i.e. 0, 3, 6 or 9).
        exponent = 3 * math.floor(math.log10(freq) / 3)

        # Rounding to 3 d.p. in Hz, as otherwise the synth can set the wrong frequency.
        freq_string = str(round(freq / (10**exponent),
                                exponent + 3)) + self.exponent_suffixes[exponent]

        response = self._query(':FREQ:' + freq_string)
        if response != 'Frequency Set':
            raise RuntimeError(
                "Unexpected response to frequency set: '{}'".format(response))

    def get_pow(self, limits=0):
        """Returns the current set power of the Holzworth synth when called without
        arguments or limits=0, and returns the maximum and minimum allowed power when
        called with limits=1 and limits =-1 respectively."""

        limits_dict = {0: '', 1: ':MAX', -1: ':MIN'}
        pow_string = self._query(':PWR' + limits_dict[limits] + '?')

        power = float(pow_string.strip(' dBm'))
        return round(power, 3)  # rounding as the synth reads to 3 d.p. precision

    def set_pow(self, power):
        """Sets the output power of the Holzworth synth."""

        if (power < self.min_pow) or (power > self.max_pow):
            raise ValueError("Power {} dBm out of range ({} to {} dBm)".format(
                power, self.min_pow, self.max_pow))

        response = self._query(':PWR:' + str(round(power, 2)) + 'dBm')
        if response != 'Power Set':
            raise RuntimeError(
                "Unexpected response to power set: '{}'".format(response))

    def identity(self):
        """Retrieves the Manufacturer, Device Name, Board Number, Firmware Version,
        Instrument Serial Number."""
        return self._query(':IDN?')

    def ping(self):
        """Needed to check connnection is alive."""
        if self.identity() == '':
            raise RuntimeError("No devices connected")
        return True

    def close(self):
        """Closes connection to the Holzworth.

        Must be called when disconnecting else future connections may not work
        """
        if self._closed:
            return
        self._closed = True
        self.dll.close_all()
        logger.info("Connection to Holzworth synth closed safely")
