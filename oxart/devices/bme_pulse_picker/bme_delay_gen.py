"""Control a BME delay generator PCI card using the vendor-supplied driver DLL."""
from ctypes import byref, cdll, c_bool, c_double, c_long, c_ulong
from dataclasses import dataclass
from enum import Enum, unique
from typing import Iterable, List, Set

import ctypes

c_bool_p = ctypes.POINTER(c_bool)
c_long_p = ctypes.POINTER(c_long)


class DelayGenException(Exception):
    """Raised on passing invalid parameters or hardware communication issues."""
    pass


def _check_status(code):
    """Convert non-zero status codes into exceptions.

    The strings are derived from the "Error Codes" page in the HLP file.
    """

    if code == 0:
        # Success.
        return code

    messages = {
        1: "Wrong product number",
        2: "Delay generator index out of range",
        3: "Delay time negative",
        4: "Incompatible trigger modes specified",
        5: "Delay time too long",
        6: "Invalid output level",
        7: "Invalid clock source",
        8: "New calibration file created",  # XXX: Not an error?!
        9: "Error writing to file",
        10: "File not found",
        11: "Low-level driver (PLX) command failed",
        12: "Communication with delay generator could not be established",
        13: "Improper ribbon cable connection to delay generator",
        14: "Proper ribbon cable connection to delay generator",  # XXX: Not an error?!
    }

    msg = messages.get(code, None)
    if not msg:
        msg = "Unknown error code: {}".format(code)
    raise DelayGenException(msg)


@unique
class StatusFlag(Enum):
    """
    Hardware status register flags.

    The definitions can be found in the "Programming BME_SG08P3" chapter of the BME_G0X
    manual, in the "Command register (read)" section.
    """
    #: channel A is active
    channel_a_active = (1 << 0)

    #: channel B is active
    channel_b_active = (1 << 1)

    #: channel C is active
    channel_c_active = (1 << 2)

    #: channel D is active
    channel_d_active = (1 << 3)

    #: channel E is active
    channel_e_active = (1 << 4)

    #: channel F is active
    channel_f_active = (1 << 5)

    #: primary trigger is active
    primary_trigger_active = (1 << 6)

    #: secondary trigger is active
    secondary_trigger_active = (1 << 7)

    #: force trigger is active
    force_trigger_active = (1 << 8)

    #: terminal count of preset register has been reached
    terminal_count_reached = (1 << 9)

    #: external clock fed via the trigger input connector is used, but no level
    #: transitions have been detected for the number of periods of the internal clock as
    #: prescribed by Multipurpose register, byte no. 6
    external_clock_no_transitions_detected = (1 << 10)

    #: all wait times for the trigger system have elapsed
    all_wait_times_elapsed = (1 << 11)

    #: Load command is active
    load_command_active = (1 << 17)


class Driver:
    """
    Interface to the driver DLL for the delay generator PCI cards by BME
    (Bergmann Messgeräte Entwicklung KG).

    There should typically only be one instance of this class per process. Note
    also that the class does not currently uninitialise and unload the DLL upon
    destruction (although that would be easily fixable), so creating many objects
    would eventually deplete the process handle pool.
    """
    def __init__(self):
        try:
            lib = cdll.DelayGenerator
        except Exception as e:
            raise DelayGenException("Failed to load delay generator DLL: {}".format(e))

        def get_fn(name, param_types, returns_status=True):
            """
            Look up a function from the DLL handle.

            If returns_status is True, applies a wrapper that converts non-zero
            status code return values into exceptions.
            """
            fn = getattr(lib, name)
            fn.argtypes = param_types
            if returns_status:
                fn.restype = lambda x: _check_status(x)
            return fn

        try:
            self.reserve_dg_data = get_fn("Reserve_DG_Data", [c_long])
            self.detect_pci_dgs = get_fn("DetectPciDelayGenerators", [c_long_p],
                                         returns_status=False)
            self.get_pci_dg = get_fn("GetPciDelayGenerator",
                                     [c_long_p, c_long_p, c_bool_p, c_long])
            self.initialize_dg = get_fn("Initialize_DG_BME", [c_long, c_long, c_long])
            self.deactivate_dg = get_fn("Deactivate_DG_BME", [c_long])
            self.activate_dg = get_fn("Activate_DG_BME", [c_long])
            self.set_gate_function = get_fn("Set_GateFunction", [c_ulong, c_long])
            self.set_trigger_parameters = get_fn("Set_TriggerParameters", [
                c_bool, c_double, c_double, c_ulong, c_ulong, c_bool, c_bool, c_bool,
                c_bool, c_bool, c_bool, c_bool, c_bool, c_long
            ])
            self.set_resetwhendone = get_fn("Set_ResetWhenDone", [c_bool, c_long])
            self.read_dg_status = get_fn("Read_DG_Status", [c_long],
                                         returns_status=False)

            # These are model-specific.
            self.set_g08_delay = get_fn("Set_G08_Delay", [
                c_ulong, c_double, c_double, c_ulong, c_ulong, c_ulong, c_bool, c_bool,
                c_bool, c_bool, c_bool, c_long
            ])
            self.set_g08_clock_parameters = get_fn(
                "Set_G08_ClockParameters",
                [c_bool, c_ulong, c_ulong, c_ulong, c_ulong, c_long])
            self.set_g08_trigger_parameters = get_fn("Set_G08_TriggerParameters", [
                c_bool, c_double, c_double, c_bool, c_bool, c_double, c_double, c_ulong,
                c_ulong, c_long
            ])
        except Exception as e:
            raise DelayGenException("Error binding to function from DLL: {}".format(e))

    def init_single_pci_card(self):
        """
        For a system with a single delay generator card installed, detect the
        parameters of that card and return an interface to it.

        Currently, only the model BME_SG08p is supported.
        """

        self.reserve_dg_data(1)

        # This function is the odd one out in that it returns the numerical
        # result and writes the status code to a pointer parameter.
        status = c_long(0)
        device_count = self.detect_pci_dgs(byref(status))
        _check_status(status.value)

        # We currently support only one delay generator card, which is a
        # gratuitous limitation. To lift it, the API needs to expose the list of
        # delay generators to the user and a way of disambiguating between them.
        DG_IDX = 0

        if device_count < 1:
            raise DelayGenException("No PCI delay generator detected.")
        elif device_count > 1:
            raise DelayGenException("More than one PCI delay generator "
                                    "detected; currently not supported.")
        return BME_SG08p(self, DG_IDX)


@unique
class ClockSource(Enum):
    """The main clock for the delay generator card to use."""

    #: Use the on-board 160 MHz oscillator.
    internal = 0,

    #: Use an external 80 MHz clock fed to the trigger input.
    external_80_mhz = 1,


@unique
class OutputGateMode(Enum):
    """Modes for the delay generator to combine pairs of adjacent channels
    instead of directly routing them to the respective outputs."""

    #: Route channels to the respective outputs.
    direct = 0

    #: Combine the two channels with a logical OR and send the result to both
    #: outputs.
    gate_or = 1

    #: Combine the two channels with a logical AND and send the result to both
    #: outputs.
    gate_and = 2

    #: Combine the two channels with an XOR-type operation and send the result
    #: to both outputs. Note that this is not an actual XOR which would produce
    #: two pulses at the output in the general case. Instead, the hardware seems
    #: to do some extra gating to only output a single pulse.
    gate_xor = 3


@dataclass
class PulseParameters:
    """Timing parameters for a single delay channel on the card."""

    #: Whether to generate a pulse on the channel at all.
    enabled: bool

    #: The delay of the pulse in microseconds, relative to the sequence start.
    delay_us: float

    #: The width of the pulse in microseconds.
    width_us: float


class BME_SG08p:
    """
    Interface to a BME SG08p delay generator card.

    Many settings (trigger inputs, etc.) are currently hard-coded to match a
    specific application in the Oxford Old Lab, and should be made configurable
    for a general-purpose driver.

    :param driver_lib: A handle to the driver DLL.
    :param device_idx: The index of the device to use, as per the DLL's conception.
    """

    CHANNEL_COUNT = 6

    # By default, the delay generator card is configured to use a 10 MHz clock
    # derived from the internal oscillator. The manufacturer suggested using a
    # higher clock rate for our application to cut down on various internal
    # delays, 40 MHz. The timing values are not automatically rescaled by the
    # driver, so we need to manually stretch them.
    #
    # After a while in continuous use, timing issues occurred with the 40 MHz
    # clock, though, causing edges on some channels to be deterministically
    # placed incorrectly. For now, a 10 MHz clock is used.
    CLOCK_FACTOR = 1

    def __init__(self, driver_lib, device_idx):
        self._lib = driver_lib
        self._device_idx = device_idx

        product_id = c_long(-1)
        slot_id = c_long(-1)
        is_master = c_bool(False)
        self._lib.get_pci_dg(product_id, slot_id, is_master, self._device_idx)
        if product_id.value != 46:
            raise DelayGenException(
                "Detected delay generator with invalid "
                "product id '{}'; currently only BME_SG08p is supported.".format(
                    product_id))
        if not is_master:
            raise DelayGenException("Detected delay generator is not set to "
                                    "master mode")
        self._lib.initialize_dg(slot_id, product_id, self._device_idx)
        self.reset()

    def reset(self) -> None:
        """
        Reset the card configuration to the default state, with the default
        trigger settings, no special gate functions enabled and all the delay
        channels being disabled.
        """

        self._deactivate_safely()

        # Set the default hardware configuration. This is application-specific
        # and should be made configurable for a proper, comprehensive driver.

        self._set_clock_params(ClockSource.internal)
        # Default to external gating and no inhibit time.
        self._set_trigger_params(True, 0.0)
        self._lib.set_g08_trigger_parameters(
            True,  # 50Ω-terminate gate input
            1.0,  # Gate input level, in V
            0.0,  # No gate delay
            True,  # Ignore gate inputs while trigger inhibited (no memoizing)
            False,  # Do not "synchronize" gate (which would use width of pulse
            # for secondary trigger)
            0.0,  # Do not force re-trigger (time in μs)
            0.0,  # No time-list step back (time in μs)
            1,  # No burst triggering. Setting this to 0 seems to break external
            # triggering.
            0xfc,  # Default flags from manual UI (send local primary/force,
            # resync pre-scaled m/s clock to input, send step-back/start/
            # inhibit/load-data)
            self._device_idx)

        # All "straight" delay channels, no combining.
        self._lib.set_gate_function(0, self._device_idx)

        # Disable all channels.
        for i in range(self.CHANNEL_COUNT):
            self._set_delay_channel(i, PulseParameters(False, 0.0, 0.0))

        self._lib.activate_dg(self._device_idx)

    def set_clock_source(self, source: ClockSource) -> None:
        """
        """
        self._deactivate_safely()
        self._set_clock_params(source)
        self._lib.activate_dg(self._device_idx)

    def _set_clock_params(self, source: ClockSource):
        if source == ClockSource.internal:
            s = 1
        elif source == ClockSource.external_80_mhz:
            s = 2
        else:
            raise DelayGenException("Unrecognised clock source")

        int_divider = int(16 / self.CLOCK_FACTOR)
        ext_divider = int(8 / self.CLOCK_FACTOR)
        return self._lib.set_g08_clock_parameters(
            True,  # Enable clock circuit
            int_divider,  # Internal oscillator divider (160 MHz base
            # frequency)
            ext_divider,  # Trigger input divider (80 MHz input assumed)
            1,  # Trigger input multiplier
            s,  # 1: crystal, 2: trigger in, 3: trigger in with
            # crystal as fallback, 4: master/slave bus
            self._device_idx)

    def set_trigger(self, use_external_gate: bool, inhibit_us: float) -> None:
        """
        """
        self._deactivate_safely()
        self._set_trigger_params(use_external_gate, inhibit_us)
        self._lib.activate_dg(self._device_idx)

    def _set_trigger_params(self, use_external_gate, inhibit_us):
        return self._lib.set_trigger_parameters(
            True,  # 50 Ω-terminate trigger input
            inhibit_us * self.CLOCK_FACTOR,  # Inhibit time
            0.0,  # Trigger level ([-2.5, 2.5] V)
            0,  # Pre-set trigger counter limit (disabled below)
            1,  # Gate divider, 0 for level-sensitive gate
            True,  # Trigger on positive external gate edge
            True,  # Use internal trigger
            False,  # No arming based on internal clock
            False,  # No software trigger
            False,  # Do not use external trigger (used for clock input)
            False,  # Do not stop when pre-set counter value is reached
            True,  # Reset all outputs 2 μs after all delays have elapsed
            not use_external_gate,  # Whether to always enable trigger regardless
            # of the gate signal
            self._device_idx)

    def set_output_gates(self, modes: Iterable[OutputGateMode]) -> None:
        """
        """
        mode_ab, mode_cd, mode_ef = modes

        # The hardware goes into xor pulse mode if both flags are set.
        OR = [OutputGateMode.gate_or, OutputGateMode.gate_xor]
        AND = [OutputGateMode.gate_and, OutputGateMode.gate_xor]

        flags = 0x0
        if mode_ab in OR:
            flags |= 0x10000
        if mode_ab in AND:
            flags |= 0x20000

        if mode_cd in OR:
            flags |= 0x40000
        if mode_cd in AND:
            flags |= 0x80000

        if mode_ef in OR:
            flags |= 0x100000
        if mode_ef in AND:
            flags |= 0x200000

        self._deactivate_safely()
        self._lib.set_gate_function(flags, self._device_idx)
        self._lib.activate_dg(self._device_idx)

    def set_pulse_parameters(self, params: List[PulseParameters]) -> None:
        """
        """
        if len(params) != self.CHANNEL_COUNT:
            raise DelayGenException("Expected one pulse parameter specification "
                                    "for each of the {} channels, not {}".format(
                                        self.CHANNEL_COUNT, len(params)))

        self._deactivate_safely()
        for i, p in enumerate(params):
            self._set_delay_channel(i, p)
        self._lib.activate_dg(self._device_idx)

    def _deactivate_safely(self):
        """
        Deactivate the delay generator without interrupting any currently running
        sequences.
        """
        # The below procedure is in line with what the BME_G0X help recommends in the
        # "Modifying Parameters Synchronuously" [sic] section.
        #
        # 2020 update to Windows 10 driver: The all_wait_times_elapsed status flag
        # seems not be set initially. Therefore, don't call this method after
        # initialisation.
        self._lib.set_resetwhendone(False, self._device_idx)
        while not self._safe():
            pass
        self._lib.deactivate_dg(self._device_idx)
        self._lib.set_resetwhendone(True, self._device_idx)

    def _read_status_word(self):
        return self._lib.read_dg_status(self._device_idx)

    def read_status_flags(self) -> Set[StatusFlag]:
        """
        """
        status_word = self._read_status_word()

        result = set()
        for flag in StatusFlag:
            # print("{}: {}".format(flag, status_word&flag.value))
            if status_word & flag.value:
                result.add(flag)

        return result

    def _safe(self):
        flags = self.read_status_flags()
        active = StatusFlag.primary_trigger_active in flags
        elapsed = StatusFlag.all_wait_times_elapsed in flags
        return elapsed or not active

    def _set_delay_channel(self, idx, params):
        CHANNEL_A_IDX = 2
        return self._lib.set_g08_delay(
            CHANNEL_A_IDX + idx,  # Channel index
            params.delay_us * self.CLOCK_FACTOR,  # Time to first edge, in μs
            params.width_us *
            self.CLOCK_FACTOR,  # Pulse width (first to second edge), in μs
            1,  # Modulo counter length
            0,  # Modulo counter offset
            0x1 if params.enabled else 0x0,  # Trigger from local primary if enabled
            True,  # Positive polarity
            False,  # Do not 50 Ω-terminate internally (for 50 Ω sink)
            False,  # Do not disconnect output stage
            False,  # Do not connect onto master/slave bus
            True,  # Positive input polarity (ignored in output mode)
            self._device_idx)
