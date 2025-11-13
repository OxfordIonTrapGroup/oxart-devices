import time
import serial
import sys
import logging
import asyncio
import numpy as np

logger = logging.getLogger(__name__)


class ArduinoDAC:

    def __init__(self, serial_name, n_channels=16, v_min=-10, v_max=10):
        """serial_name : serial port name
        n_channels : clock frequency in Hz
        v_min, v_max: min and max voltages the DAC can produce
        """

        self.port = serial.Serial(serial_name, baudrate=115200, timeout=2)

        self.n_channels = n_channels
        self.v_min = v_min
        self.v_max = v_max

        time.sleep(3)
        logger.info("Connected to ArduinoDAC with ID '{}'".format(self.identity()))

        # Array of the last set voltages
        self._voltages = np.zeros(n_channels)
        for i in range(n_channels):
            self._voltages[i] = np.nan

    def _send_command(self, command):
        try:
            self.port.write((command + '\n').encode())
        except serial.SerialTimeoutException:
            logger.exception("Serial write timeout: Force exit")
            # This is hacky but makes the server exit
            asyncio.get_event_loop().call_soon(sys.exit, 42)
            raise

    def _read_line(self):
        """Read a CR terminated line.

        Returns '' on timeout
        """
        s = ''
        while len(s) == 0 or s[-1] != '\n':
            c = self.port.read().decode()
            if c == '':  # Timeout
                raise Exception('Serial read timeout')
            s += c
        return s

    def _validate_channel_index(self, channel):
        """Check whether a channel index is in range.

        Returns true if channel is in range.
        """

        if channel < 0 or channel >= self.n_channels:
            return False
        else:
            return True

    def _validate_voltage(self, voltage):
        """Check whether a voltage is in range.

        Returns true if voltage is in range.
        """

        if voltage < self.v_min or voltage > self.v_max:
            return False
        else:
            return True

    def set_voltage(self, channel, voltage, update=True):
        """Set the voltage on the given channel.

        Voltage is a float with units of volts. Update determines whether to the output
        should be updated on execution of this command, or later with 'update'
        """
        if update:
            command = 'VU'
        else:
            command = 'V'

        if not self._validate_channel_index(channel):
            raise Exception("Bad channel index: {}".format(channel))

        command += ' {}'.format(channel)

        if not self._validate_voltage(voltage):
            raise Exception("Bad voltage: {}".format(voltage))

        command += ' {:.4f}\n'.format(voltage)

        self._send_command(command)

        self._voltages[channel] = voltage

        logger.info("Setting voltage channel {} to {}".format(channel, voltage))

    def get_voltage(self, channel):
        """Reads the voltage on the given channel."""

        if not self._validate_channel_index(channel):
            raise Exception("Bad channel index: {}".format(channel))

        return self._voltages[channel]

        # command = 'V? {}\n'.format(channel)

        # self._send_command(command)

        # response = self._read_line().split()
        # if response[0] != "V":
        #     print(response)
        #     raise Exception("Device responded incorrectly")

        # try:
        #     value = float(response[1])
        # except ValueError:
        #     raise ValueError("Could not interpret device response as a float")

        # return value

    def reset(self):
        self._send_command("reset")

    def identity(self):
        self._send_command("*IDN?")
        return self._read_line().strip()

    def ping(self):
        return True
