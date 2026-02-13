class CommandSerde:
    """Manages de/serialization of commands used to communicate with a Windfreak."""

    encoding = "utf-8"

    def __init__(
        self,
        cmd: str,
        dtype: type | None = None,
        precision: int = 0,
        vrange: tuple | None = None,
        queriable: bool = True,
        needs_channel: bool = False,
        writeable: bool = True,
    ):
        self.cmd_str = cmd
        self.cmd = bytes(cmd, self.encoding)
        self.queriable = queriable
        self.dtype = dtype
        self.needs_channel = needs_channel

        if dtype is int:
            precision = 0
        elif dtype is bool:
            precision = 0
            vrange = (0, 1)

        self.writeable = writeable

        self.dtype = dtype
        self.precision = precision
        self.vrange = vrange

    def __eq__(self, value: "CommandSerde") -> bool:
        return self.cmd == value.cmd

    def query(self):
        if not self.queriable:
            raise ValueError(f"Command '{self.cmd_str}' cannot be queried")

        if self.writeable:
            return self.cmd + bytes("?", self.encoding)
        else:
            return self.cmd

    def deserialise(self, serial_data: bytes):
        response_str = serial_data.decode(self.encoding).strip()
        if self.queriable:
            if self.dtype is bool:
                return self.dtype(int(response_str))
            return self.dtype(response_str)  # type: ignore
        else:
            raise ValueError(f"Command '{self.cmd_str}' is not queriable")

    def serialise(self, value) -> tuple[bytes, str]:
        """Serialise a value associated with this command. May modify the value (e.g.
        convert a bool to an int or round a float).

        :return: (bytes to send, str[value requested])
        """
        if value is None:
            return (self.cmd, "")

        if not self.writeable:
            raise ValueError(f"Command '{self.cmd_str}' does not take a value")

        if self.dtype is bool:
            value = int(value)

        if self.vrange is not None and not self.vrange[0] <= value <= self.vrange[1]:
            raise ValueError(f"Value {value} out of range for command '{self.cmd_str}'")

        value_str = f"{value:.{self.precision}f}"
        return (self.cmd + bytes(value_str, self.encoding), value_str)


_frequency_kwargs = {"dtype": float, "precision": 3}
_abs_frequency_range = (53.0, 13999.9999999)
_power_kwargs = {"dtype": float, "precision": 3, "vrange": (-20.0, 60.0)}

device_level_commands = {
    "control_channel": CommandSerde(
        "C",
        int,
        vrange=(0, 1),
    ),
    "ref_clk": CommandSerde(
        "x",
        int,
        vrange=(0, 2),
    ),
    "pll_locked": CommandSerde(
        "p",
        bool,
        writeable=False,
    ),
    "save_eeprom": CommandSerde(
        "e",
        queriable=False,
    ),
    "device_serial_number": CommandSerde(
        "-",
        int,
        writeable=False,
    ),
    "device_model_type": CommandSerde(
        "+",
        str,
        writeable=False,
    ),
    "temperature_C": CommandSerde(
        "z",
        float,
        writeable=False,
    ),
}

static_control_commands = {
    "frequency_now_MHz":
    CommandSerde(
        "f",
        **_frequency_kwargs,
        vrange=_abs_frequency_range,
        needs_channel=True,
    ),
    "power_dBm":
    CommandSerde(
        "W",
        **_power_kwargs,
        needs_channel=True,
    ),
    "enable_rf":
    CommandSerde(
        "E",
        bool,
        needs_channel=True,
    ),
    "mute_rf":
    CommandSerde(
        "h",
        bool,
        needs_channel=True,
    ),
    "increment_current_phase":
    CommandSerde(
        "~",
        int,
        3,
        queriable=False,
        needs_channel=True,
    ),
}

sweep_commands = {
    "sweep_freq_lower_MHz":
    CommandSerde(
        "l",
        **_frequency_kwargs,
        vrange=_abs_frequency_range,
        needs_channel=True,
    ),
    "sweep_freq_upper_MHz":
    CommandSerde(
        "u",
        **_frequency_kwargs,
        vrange=_abs_frequency_range,
        needs_channel=True,
    ),
    "sweep_freq_step_MHz":
    CommandSerde(
        "s",
        **_frequency_kwargs,
        vrange=(0.0, 13999.9999999),
        needs_channel=True,
    ),
    "sweep_time_step_ms":
    CommandSerde(
        "t",
        float,
        3,
        vrange=(4, 10000),
        needs_channel=True,
    ),
    "sweep_power_low_dBm":
    CommandSerde(
        "[",
        **_power_kwargs,
        needs_channel=True,
    ),
    "sweep_power_high_dBm":
    CommandSerde(
        "]",
        **_power_kwargs,
        needs_channel=True,
    ),
    "sweep_low_to_high":
    CommandSerde(
        "^",
        bool,
        needs_channel=True,
    ),
    "run_sweep":
    CommandSerde(
        "g",
        bool,
        needs_channel=True,
    ),
    "sweep_continuously":
    CommandSerde(
        "c",
        bool,
        needs_channel=True,
    ),
}
