import logging
import serial
import sys
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)

PsuType = Enum("PsuType", ["QL355P", "QL355TP"])


class QL355:
    """Driver for TTI QL355P (single channel) and QL355TP (two channel
    + aux channel) power supplies.

    QL355P: Single channel PSU
    QL355TP: Two channel PSU (ch 0 & 1), with an auxillary channel (ch 2)
    that can be enabled/disabled, but voltage and current cannot be set.

    Note that this driver does not set the output range of the PSU
    automatically

    All voltages are in Volts, and currents in Amps."""

    def __init__(self, serial_addr):
        self.port = serial.Serial(
            serial_addr,
            baudrate=19200,
            timeout=0.1,
            write_timeout=0.1)
        self._purge()

        ident = self.identity()
        if ident.startswith("THURLBY-THANDAR,QL355P"):
            self.type = PsuType.QL355P
        elif ident.startswith("THURLBY-THANDAR,QL355TP"):
            self.type = PsuType.QL355TP
        else:
            raise Exception("Unsupported PSU type '{}'".format(ident))
        logger.info("Connected to {}".format(self.type))

    def _purge(self):
        """Make sure we start from a clean slate with the controller"""
        # Send a carriage return to clear the controller's input buffer
        self.port.write('\r'.encode())
        # Read any old gibberish from input until a timeout occurs
        c = 'c'
        while c != '':
            c = self.port.read().decode()

    def close(self):
        """Close the serial port."""
        self.port.close()

    def _send_command(self, cmd):
        try:
            self.port.write((cmd+'\r\n').encode())
        except serial.SerialTimeoutException as e:
            logger.exception("Serial write timeout: Force exit")
            # This is hacky but makes the server exit
            asyncio.get_event_loop().call_soon(sys.exit, 42)
            raise

    def _read_line(self):
        """Read a CR terminated line. Returns '' on timeout"""
        s = ''
        while len(s) == 0 or s[-1] != '\r':
            c = self.port.read().decode()
            if c == '':  # Timeout
                break
            s += c
        return s

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
        """Sets the voltage limit for channel"""
        self._check_valid_channel(channel)
        if voltage < 0:
            raise ValueError("Voltage limit must be positive")
        self._send_command("V{} {}".format(channel+1, voltage))

    def get_voltage_limit(self, channel=0):
        """Returns the voltage limit for channel"""
        self._check_valid_channel(channel)
        self._send_command("V{}?".format(channel+1))
        response = self._read_line().split()
        if response[0] != "V{}".format(channel+1):
            raise Exception("Device responded incorrectly")
        try:
            val = float(response[1])
        except ValueError:
            raise ValueError("Could not interpret device response as a float")
        return val

    def set_current_limit(self, current, channel=0):
        """Sets the current limit for channel"""
        self._check_valid_channel(channel)
        if current < 0:
            raise ValueError("Current limit must be positive")
        self._send_command("I{} {}".format(channel+1, current))

    def get_current_limit(self, channel=0):
        """Returns the current limit for channel"""
        self._check_valid_channel(channel)
        self._send_command("I{}?".format(channel+1))
        response = self._read_line().split()
        if response[0] != "I{}".format(channel+1):
            raise Exception("Device responded incorrectly")
        try:
            val = float(response[1])
        except ValueError:
            raise ValueError("Could not interpret device response as a float")
        return val

    def set_output_enable(self, enable, channel=0):
        """Enable / disable a channel"""
        self._check_valid_channel(channel, is_enable=True)
        # enable flag needs to be 0 or 1, hence int(bool) dance
        self._send_command("OP{} {}".format(channel+1, int(bool(enable))))

    def get_voltage(self, channel=0):
        """Returns the actual output voltage"""
        self._check_valid_channel(channel)
        self._send_command("V{}O?".format(channel+1))
        response = self._read_line().strip()
        try:
            val = float(response[0:-1])
        except ValueError:
            raise ValueError("Could not interpret device response as a float")
        return val

    def get_current(self, channel=0):
        """Returns the actual output current"""
        self._check_valid_channel(channel)
        self._send_command("I{}O?".format(channel+1))
        response = self._read_line().strip()
        try:
            val = float(response[0:-1])
        except ValueError:
            raise ValueError("Could not interpret device response as a float")
        return val

    def identity(self):
        """Returns the identity string of the device"""
        self._send_command("*IDN?")
        return self._read_line()

    def ping(self):
        self.identity()
        return True
