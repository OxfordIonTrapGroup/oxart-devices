# API reference:
#   https://windfreaktech.com/wp-content/uploads/2016/12/WFT_SerialProgramming_API_10b.pdf

import enum
from contextlib import contextmanager
from logging import getLogger

from serial import Serial, SerialException, SerialTimeoutException

from oxart.devices.windfreak_synthhd.commands import (
    device_level_commands,
    static_control_commands,
    sweep_commands,
)

logger = getLogger(__name__)


@enum.unique
class SynthHDChannel(enum.Enum):
    RF_OUT_A = 0
    RF_OUT_B = 1


class SerialDevice:
    commands = {}

    def __init__(self, port, **serial_kwargs):
        self.serial_port = Serial(**serial_kwargs)
        self.serial_port.port = port

    def open(self):
        self.serial_port.open()
        self.serial_port.reset_input_buffer()

    def close(self):
        self.serial_port.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def query_cmd(self, command):
        cmd = self.commands[command]
        if not cmd.queriable:
            raise ValueError(f"Command '{command}' cannot be queried")

        query = cmd.query()

        try:
            logger.debug(f"Querying '{command}': '{query}'")
            self.serial_port.write(query)

            response = cmd.deserialise(self.serial_port.readline())
            logger.debug(f"Received response for '{command}': '{response}'")
            return response
        except SerialTimeoutException as e:
            logger.error(f"Timeout while querying '{command}':\n{e}")
            raise

    def send_cmd(self, command, value):
        cmd = self.commands[command]
        if not cmd.writeable:
            raise ValueError(f"Command '{command}' cannot be written to")

        data, value_str = cmd.serialise(value)
        try:
            logger.debug(f"Writing '{command}' with value '{value_str}': '{data}'")
            self.serial_port.write(data)
        except SerialTimeoutException:
            logger.error(f"Timeout while writing '{command}': {data}")
            raise
        return value_str

    def query_raw_cmd(self, cmd_bytes: bytes):
        self.serial_port.write(cmd_bytes)
        response = self.serial_port.readline()
        logger.debug(f"Received response for '{cmd_bytes}': '{response}'")
        return response

    def send_raw_cmd(self, cmd_bytes: bytes):
        logger.debug(f"Writing command '{cmd_bytes}'")
        self.serial_port.write(cmd_bytes)


class WindfreakSynthHD(SerialDevice):
    commands = {**static_control_commands, **sweep_commands, **device_level_commands}

    def __init__(self, port, timeout=3, **serial_kwargs):
        write_timeout = serial_kwargs.pop("write_timeout", timeout)
        super().__init__(
            port, timeout=timeout, write_timeout=write_timeout, **serial_kwargs
        )
        self._active_control_channel = None

    def open(self):
        super().open()
        serial_num, model_type = self.read_device_info()
        logger.info(
            "Connected to Windfreak SynthHD "
            f"(Serial: {serial_num}, Model: {model_type}) at port {self.serial_port.port}"
        )

    def ping(self):
        logger.debug("Pinging device...")
        try:
            self.query_cmd("device_serial_number")
            return True
        except SerialException:
            return False

    @contextmanager
    def control_channel(self, channel: SynthHDChannel | None):
        """Context manager to temporarily set the controlled channel for a block of commands."""
        if channel is None:
            if self._active_control_channel is None:
                raise RuntimeError(
                    "No channel specified and no active control channel set"
                )
        else:
            active_control_channel = self._active_control_channel
            self.set_controlled_channel(channel)

        try:
            yield channel
        finally:
            if channel is not None and (active_control_channel is not None):
                self.set_controlled_channel(active_control_channel)

    def send_cmd(self, command, value=None):
        """
        Sends a (write-only) serial command to the synthhd without expecting a response.
        """
        logger.debug(
            f"Setting {command} to {value} on channel {self._active_control_channel}"
        )
        if (
            self.commands[command].needs_channel
            and self._active_control_channel is None
        ):
            raise RuntimeError(f"Command '{command}' needs a channel to be specified.")
        return super().send_cmd(command, value)

    def query_cmd(self, command):
        """
        Sends a (read-only) serial command to the synthhd and returns the response.
        If a `channel` is specified, restores the previously active channel (if set) after execution.
        """
        if (
            self.commands[command].needs_channel
            and self._active_control_channel is None
        ):
            raise RuntimeError(f"Command '{command}' needs a channel to be specified.")

        logger.debug(f"Querying {command} on channel {self._active_control_channel}")
        return super().query_cmd(command)

    def read_device_info(self):
        """Reads device information.
        :return: (device_serial_number, device_model_type)
        """
        info = {}
        for key in ["device_serial_number", "device_model_type"]:
            info[key] = self.query_cmd(key)

        return (info["device_serial_number"], info["device_model_type"])
        # return (None, None)

    def enable_rf(self, enable: bool):
        """Enable or disable the RF output."""
        return self.send_cmd("enable_rf", enable)

    def is_rf_enabled(self) -> bool:
        return self.query_cmd("enable_rf")

    def mute_rf(self, mute: bool):
        """Mute or unmute the RF output."""
        return self.send_cmd("mute_rf", mute)

    def set_controlled_channel(self, channel: SynthHDChannel):
        """Set the active channel to control for all subsequent commands."""
        logger.info("Changing active control channel to {}".format(channel))

        self.send_cmd("control_channel", channel.value)
        self._active_control_channel = channel

    def get_controlled_channel(self) -> SynthHDChannel:
        """Get the current controlled channel."""
        channel_value = self.query_cmd("control_channel")
        self._active_control_channel = SynthHDChannel(channel_value)

        return self._active_control_channel

    def set_frequency(self, frequency_Hz: float):
        """Set the frequency of the specified channel."""
        return self.send_cmd("frequency_MHz", frequency_Hz / 1e6)

    def get_frequency_now(self) -> float:
        """
        Get the frequency in Hz of the specified channel.
        Returns the current frequency when a sweep is running.
        """
        return self.query_cmd("frequency_MHz") * 1e6

    def set_power(self, power_dBm: float):
        """Set the power of the specified channel."""
        return self.send_cmd("power_dBm", power_dBm)

    def get_power_now(self) -> float:
        """
        Get the power in dBm of the specified channel.
        Returns the current power when a sweep is running.
        """
        return self.query_cmd("power_dBm")

    def pause_sweep(self):
        """Pause a currently running frequency sweep."""
        return self.send_cmd("run_sweep", False)

    def start_sweep(self):
        """Starts a frequency sweep.
        If sweep_continuously is False
            * Resumes the current sweep if it is paused.
            * Starts a new sweep with the last configured parameters if the previous sweep has finished.
        If sweep_continuously is True, restarts the current sweep from the beginning
        """
        return self.send_cmd("run_sweep", True)

    def save_eeprom(self):
        """Save the current device state to EEPROM."""
        return self.send_cmd("save_eeprom", None)

    def is_sweep_running(self) -> bool:
        """Check if a frequency sweep is currently running."""
        return self.query_cmd("run_sweep")

    def configure_frequency_sweep(
        self,
        start_frequency_Hz: float,
        end_frequency_Hz: float,
        step_frequency_Hz: float,
        step_time: float,
        start_power: float,
        end_power: float | None = None,
        sweep_continuously: bool = False,
    ):
        """
        Configure a frequency sweep on the SynthHD.
        * Does not start the sweep.
        * Stops any currently running sweep.

        :param start_frequency: Frequency at start of sweep [Hz]
        :param end_frequency: Frequency at end of sweep [Hz]
        :param step_frequency: Step size for frequency [Hz]
        :param step_time: Time between consecutive steps [s]
        :param start_power: Power at start of sweep [dBm]
        :param end_power: Power at end of sweep [dBm]. If None, power is not swept and remains at start_power.
        :param sweep_continuously: Restart sweep automatically after end of sweep?
        """

        if step_frequency_Hz > abs(end_frequency_Hz - start_frequency_Hz):
            raise ValueError("Step frequency must be smaller than the frequency range")

        if end_power is None:
            end_power = start_power

        if start_frequency_Hz < end_frequency_Hz:
            sweep_low_to_high = True
            lower_freq_MHz, upper_freq_MHz = (
                start_frequency_Hz / 1e6,
                end_frequency_Hz / 1e6,
            )
        else:
            sweep_low_to_high = False
            lower_freq_MHz, upper_freq_MHz = (
                end_frequency_Hz / 1e6,
                start_frequency_Hz / 1e6,
            )

        step_time_ms = step_time * 1000
        step_frequency_MHz = step_frequency_Hz / 1e6

        self.send_cmd("run_sweep", False)

        self.send_cmd("sweep_freq_lower_MHz", lower_freq_MHz)
        self.send_cmd("sweep_freq_upper_MHz", upper_freq_MHz)
        self.send_cmd("sweep_freq_step_MHz", step_frequency_MHz)
        self.send_cmd("sweep_step_time_ms", step_time_ms)
        self.send_cmd("sweep_power_low_dBm", start_power)
        self.send_cmd("sweep_power_high_dBm", end_power)
        self.send_cmd("sweep_low_to_high", sweep_low_to_high)
        self.send_cmd("sweep_continuously", sweep_continuously)
