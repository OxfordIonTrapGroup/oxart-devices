import logging
import serial
import os
import re
import sys
import asyncio
import appdirs

import sipyco.pyon as pyon

logger = logging.getLogger(__name__)


def _get_data_dir():
    """Get the name of the data directory and create it if necessary."""
    dir_ = appdirs.user_data_dir("oxart-devices", "oitg")
    os.makedirs(dir_, exist_ok=True)
    return dir_


class PiezoController:
    """Driver for Thorlabs MDT693B 3 channel open-loop piezo controller.

    Tested with firmware versions 1.06 and 1.09.
    """

    def __init__(self, serial_addr):
        self.port = serial.serial_for_url(
            serial_addr, baudrate=115200, timeout=0.1, write_timeout=0.1
        )

        self.echo = None
        self._purge()

        firmware = self.get_firmware_version()
        if firmware < "1.09":
            self._set = self._set_1_06
            self._get = self._get_1_06
            self._reset_input = self._reset_input_timeout
        elif firmware >= "1.09":
            self._set = self._set_1_09
            self._get = self._get_1_09
            self._reset_input = self._reset_input_1_09
        else:
            raise DriverError("Firmware version '{}' not recognised".format(firmware))

        self._set_echo(False)
        self.v_limit = self.get_voltage_limit()
        logger.info("Device vlimit is {}".format(self.v_limit))

        self.data_dir = _get_data_dir()
        self.filename = "piezo_{}.pyon".format(self.get_serial())
        self.abs_filename = os.path.join(self.data_dir, self.filename)
        self.channels = {"x": -1, "y": -1, "z": -1}
        self._load_setpoints()

    def close(self):
        """Close the serial port."""
        self.port.close()

    def feedback_enabled(self):
        # For API compatibility with BPC303 driver.
        return False

    #
    # Basic sending/receiving operations
    #
    def _send(self, cmd):
        """Wrapper for send that will exit server if error occurs."""
        try:
            str_ = cmd + "\r"
            logger.debug("Sending " + repr(str_))
            self.port.write(str_.encode())
        except serial.SerialTimeoutException:
            logger.exception("Serial write timeout: Force exit")
            # This is hacky but makes the server exit
            asyncio.get_event_loop().call_soon(sys.exit, 42)
            raise

    def _send_command(self, cmd):
        self._send(cmd)
        if self.echo:
            # Read off the echoed command to stay in sync
            _ = self._read_line()

    def _read_line(self):
        """Read a CR terminated line.

        Returns '' on timeout
        """
        line = ""
        while len(line) == 0 or line[-1] != "\r":
            c = self.port.read().decode()
            if c == "":
                # Timeout occurred
                break
            line += c
        logger.debug("Read " + repr(line))
        return line

    def _purge(self):
        """Make sure we start from a clean slate with the controller."""
        self._send("")
        self._reset_input_timeout()

    def _reset_input_timeout(self):
        """Read everything off the input and discard."""
        _ = self.port.read().decode()
        while _ != "":
            _ = self.port.read().decode()

    def _reset_input(self):
        """Reset the input.

        Firmware version specific.
        """
        raise NotImplementedError

    def _set(self, *args, **kwargs):
        """Send a set type command.

        Firmware version specific.
        """
        raise NotImplementedError

    def _get(self, *args, **kwargs):
        """Send a get type command.

        Firmware version specific.
        """
        raise NotImplementedError

    def _get_float(self, cmd, **kwargs):
        response = self._get(cmd, **kwargs)
        return float(self._strip_brackets(response))

    def _get_multiline(self, cmd, **kwargs):
        """Has to wait for timeout."""
        cmd_str = "{}?".format(cmd)
        self._send_command(cmd_str)
        para = ""
        line = self._read_line()
        while line != "":
            para += line
            line = self._read_line()
        return para.replace("\r", "\n")

    #
    # v1.06
    #
    def _set_1_06(self, cmd, val, check=False):
        """<= v1.06 set command."""
        cmd_str = "{}={}".format(cmd, val)
        self._send_command(cmd_str)

        if check:
            self._check_1_06()
        else:
            _ = self.port.read().decode()

    def _get_1_06(self, cmd, check=False):
        """<= v1.06 get command."""
        cmd_str = "{}?".format(cmd)
        self._send_command(cmd_str)

        if check:
            self._check_1_06()
        else:
            _ = self.port.read().decode()

        return self._read_line().strip()

    def _check_1_06(self):
        c = self.port.read().decode()
        if c == "*":
            return None
        elif c == "!":
            raise CommandNotDefined()
        else:
            raise ParseError()

    #
    # v1.09
    #
    def _set_1_09(self, cmd, val, check=True):
        """>= v1.09 set command."""
        cmd_str = "{}={}".format(cmd, val)
        self._send_command(cmd_str)

        if check:
            self._check_1_09()
        else:
            self._reset_input_1_09()

    def _get_1_09(self, cmd, check=True):
        """>= v1.09 get command."""
        cmd_str = "{}?".format(cmd)
        self._send_command(cmd_str)

        response = self._read_line().strip()

        if check:
            self._check_1_09()
        else:
            self._reset_input_1_09()

        return response

    def _check_1_09(self):
        c = self.port.read().decode()
        if c == ">":
            return None
        else:
            s = c
            while s[-1] != ">":
                c = self.port.read().decode()
                if c == "":
                    # Timeout occurred
                    break
                s += c
            if s == "CMD_NOT_DEFINED>":
                raise CommandNotDefined()
            else:
                raise ParseError()

    def _reset_input_1_09(self):
        _ = self.port.read().decode()
        while _ != ">" and _ != "":
            _ = self.port.read().decode()

    #
    # Get/Set commands
    #
    def _get_echo(self):
        """Get echo mode of controller."""
        response = self._get("echo")
        self.echo = response == "[Echo On]"
        return self.echo

    def _set_echo(self, enable):
        """Set echo mode of controller."""
        # NB "echo=" command is awful, in that it always elicits a response
        # of '[Echo On]\r' or '[Echo Off]\r' regardless, unlike all other set
        # commands which just set the value quietly
        self._set("echo", 1 if enable else 0, check=False)
        self._reset_input()
        self.echo = enable

    def _get_all_commands(self):
        """Get the list of recognised commands from the device.

        Equivalent to sending a single '?\r' to the device.
        """
        return self._get_multiline("")

    def get_id(self):
        """Returns the identity paragraph.

        This includes the device model, serial number, and firmware version. This
        function needs to wait for a serial timeout, hence is a little slow
        """
        # Due to the crappy Thorlabs protocol (no clear finish marker) we have
        # to wait for a timeout to ensure that we have read everything
        # (only for true for versions <1.09)
        return self._get_multiline("id")

    def get_firmware_version(self):
        id_ = self.get_id()
        match = re.search("Firmware Version: (.*)", id_)
        if match:
            return match.group(1).strip()
        # If we get here we got a timeout
        raise IOError("Timeout while reading serial string")

    def get_serial(self):
        """Returns the device serial string."""
        id_ = self.get_id()
        match = re.search("Serial#:(.*)", id_)
        if match:
            return match.group(1).strip()
        # If we get here we got a timeout
        raise IOError("Timeout while reading serial string")

    def set_channel(self, channel, voltage):
        """Set a channel (one of 'x','y','z') to a given voltage."""
        voltage = float(voltage)
        self._check_valid_channel(channel)
        self._check_voltage_in_limit(voltage)

        cmd = channel + "voltage"
        self._set(cmd, voltage)
        self.channels[channel] = voltage
        self._save_setpoints()

    def get_channel_output(self, channel):
        """Returns the current *output* voltage for a given channel.

        Note that this may well differ from the set voltage by a few volts due to ADC
        and DAC offsets.
        """
        self._check_valid_channel(channel)
        cmd = channel + "voltage"
        return self._get_float(cmd)

    def get_channel(self, channel):
        """Return the last voltage set via USB for a given channel."""
        self._check_valid_channel(channel)
        return self.channels[channel]

    def get_voltage_limit(self):
        """Returns the output limit setting in Volts.

        This is either 75V, 100V or 150V, set by the switch on the device back panel)
        """
        return self._get_float("vlimit")

    #
    # Boring check/parsing functions
    #
    def _check_valid_channel(self, channel):
        """Raises a ValueError if the channel is not valid."""
        if channel not in self.channels:
            raise ValueError("Channel must be one of 'x', 'y', or 'z'")

    def _check_voltage_in_limit(self, voltage):
        """Raises a ValueError if the voltage is not in limit for the current
        controller settings."""
        if voltage > self.v_limit or voltage < 0:
            raise ValueError(
                "Voltage must be between 0 and vlimit={}".format(self.v_limit)
            )

    def _strip_brackets(self, line):
        """Take string enclosed in square brackets and return string."""
        match = re.search(r"\[(.*)\]", line)
        if match:
            return match.group(1)
        raise ParseError("Bracketed string not found in '{}'".format(line))

    #
    # Save file operations
    #
    def _load_setpoints(self):
        """Load setpoints from a file."""
        try:
            self.channels = pyon.load_file(self.abs_filename)
            logger.info(
                "Loaded '{}', channels: {}".format(self.filename, self.channels)
            )
        except FileNotFoundError:
            logger.warning(
                "Couldn't find '{}' in '{}', no setpoints loaded".format(
                    self.filename, self.data_dir
                )
            )

    def _save_setpoints(self):
        """Write the setpoints out to file."""
        pyon.store_file(self.abs_filename, self.channels)
        logger.debug("Saved '{}', channels: {}".format(self.filename, self.channels))

    def save_setpoints(self):
        """Deprecated: setpoints are saved internally on every set command"""
        self._save_setpoints()

    #
    # ping() required - get_voltage_limit() should raise an error if something
    # is wrong
    #
    def ping(self):
        self.get_voltage_limit()
        return True


class SimulationPiezoController:

    def __init__(self, *args, **kwargs):
        logger.debug("Initialised")

    def close(self):
        logger.debug("Called close")

    def ping(self):
        logger.debug("Called ping")
        return True

    def save_setpoints(self):
        logger.debug("Called save_setpoints")


class ParseError(Exception):
    """Raised when piezo controller output cannot be parsed as expected."""


class DriverError(Exception):
    """Exception raised when this driver fails."""


class CommandNotDefined(Exception):
    """Raised if piezo controller does not recognise command."""
