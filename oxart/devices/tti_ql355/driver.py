import logging
from enum import Enum

from oxart.devices.streams import get_stream

logger = logging.getLogger(__name__)

PsuType = Enum("PsuType", ["QL355P", "QL355TP"])


class QL355:
    """Driver for TTI QL355P (single channel) and QL355TP (two channel
    + aux channel) power supplies.

    Note that this driver does not set the output range of the PSU
    automatically.

    Default TCP/IP port is port=9221
    """

    def __init__(self, device):
        self.stream = get_stream(device,
                                 baudrate=19200,
                                 timeout=0.1)
        self._purge()
        assert self.ping()

        ident = self.identify().split(',')
        if ident[1].strip() == "QL355P":
            self.type = PsuType.QL355P
        elif ident[1].strip() == "QL355TP":
            self.type = PsuType.QL355TP
        else:
            raise Exception("Unsupported PSU type '{}'".format(ident))

    def _purge(self):
        """Make sure we start from a clean slate with the controller.

        NB the stream must be configured in non-blocking mode for this method
        to return, see aqctl_tti_ql355.
        """
        # Send a carriage return to clear the controller's input buffer
        self.stream.write('\r'.encode())
        # Read any old gibberish from input until a timeout occurs
        while self.stream.read() != b"":
            pass

    def close(self):
        """Close the serial port."""
        self.stream.close()

    def _check_valid_channel(self, channel, is_enable=False):
        """Raises a ValueError if the channel number is not valid for
        this PSU type.
        is_enable is True if we want to check if this channel is valid
        only for enable commands"""

        ex = ValueError("Channel number {} not valid for {}".format(channel,
                                                                    self.type))
        if self.type is PsuType.QL355P:
            if channel != 0:
                raise ex
        elif self.type is PsuType.QL355TP:
            if channel < 0 or ((channel > 1 and not is_enable) or channel > 2):
                raise ex

    def set_voltage_limit(self, voltage, channel=0):
        """Sets the voltage limit for channel in volts"""
        self._check_valid_channel(channel)
        if voltage < 0:
            raise ValueError("Voltage limit must be positive")
        self.stream.write("V{} {}\n".format(channel+1, voltage).encode())

    def get_voltage_limit(self, channel=0):
        """Returns the voltage limit for channel in volts"""
        self._check_valid_channel(channel)
        self.stream.write("V{}?\n".format(channel+1).encode())
        response = self.stream.readline().decode().split()
        if response[0] != "V{}".format(channel+1):
            raise Exception("Device responded incorrectly")
        return float(response[1])

    def set_current_limit(self, current, channel=0):
        """Sets the current limit for channel in amps"""
        self._check_valid_channel(channel)
        if current < 0:
            raise ValueError("Current limit must be positive")
        self.stream.write("I{} {}\n".format(channel+1, current).encode())

    def get_current_limit(self, channel=0):
        """Returns the current limit for channel in amps"""
        self._check_valid_channel(channel)
        self.stream.write("I{}?\n".format(channel+1).encode())
        response = self.stream.readline().decode().split()
        if response[0] != "I{}".format(channel+1):
            raise Exception("Device responded incorrectly")
        return float(response[1])

    def set_output_enable(self, enable, channel=0):
        """Enable / disable a channel"""
        self._check_valid_channel(channel, is_enable=True)
        self.stream.write("OP{} {}\n".format(
            channel+1, int(bool(enable))).encode())

    def get_voltage(self, channel=0):
        """Returns the actual (measured) output voltage in volts"""
        self._check_valid_channel(channel)
        self.stream.write("V{}O?\n".format(channel+1).encode())
        return float(self.stream.readline().decode()[:-1])

    def get_current(self, channel=0):
        """Returns the actual (measured) output current in amps"""
        self._check_valid_channel(channel)
        self.stream.write("I{}O?\n".format(channel+1).encode())
        return float(self.stream.readline().decode()[:-1])

    def identify(self):
        """Returns device identity string"""
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def ping(self):
        """ Returns True if we are connected to a PSU, otherwise returns False.
        """
        ident = self.identify().split(',')
        if ident[0] not in ["THURLBY-THANDAR", "THURLBY THANDAR"]:
            return False
        if ident[1].strip() not in ["QL355P", "QL355TP"]:
            return False
        return True
