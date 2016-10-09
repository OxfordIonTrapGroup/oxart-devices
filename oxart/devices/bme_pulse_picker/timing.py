import copy
from .bme_delay_gen import OutputGateMode, PulseParameters

class InvalidTimingError(Exception):
    """Raised when the user specifies a set of parameters that violate the
    hardware timing constraints."""
    pass

class TimingParams:
    """Stores different pulse picker timing parameters. All times in
    microseconds."""

    # 80 MHz repetition rate
    LASER_PERIOD_US = 1.25e-3

    # The safe hardware limit is actually 50 us, but with the delay
    # generator currently running at 10 MHz, the trigger pulses themselves
    # end up being up to ~130 ns long, so be on the safe side.
    MIN_SWITCH_INTERVAL_US = 150e-3

    def __init__(self, allow_long_pulses):
        self._allow_long_pulses = allow_long_pulses

        self.offset_on_us = 0.0
        """Timing offset to apply between nominally synchronous pulses to the
        ON switches; positive meaning channel B being later."""

        self.offset_off_us = 0.0
        """Timing offset to apply between nominally synchronous pulses to the
        OFF switches; positive meaning channel B being later."""

        self.pre_open_us = 0.2
        """Wait time between initial OFF pulse and ON pair."""

        self.post_open_us = 0.2
        """Wait time between ON pair and second OFF pair."""

        self.open_us = 0.001
        """Time between ON pair (i.e. optical pulse duration)."""

        self.align_us = 0.0
        """Extra shift of the ON pair on top of pre_open_us, for useful units
        when calibrating the timing relation to the laser pulse train."""

        self.ensure_valid()

    def ensure_valid(self):
        """
        Verify that the timing parameters are sane, raising an error if not.

        This is quite important, as the hardware switches can be damaged by
        triggering them in an inadequate way.
        """

        if self.open_us < 0:
            raise InvalidTimingError("Pulse on time must not be negative")

        if (not self._allow_long_pulses) and self.open_us > 2 * self.LASER_PERIOD_US:
            raise InvalidTimingError("Pulse on time nonsensically long")

        if (self.pre_open_us - self.open_us / 2) < self.MIN_SWITCH_INTERVAL_US:
            raise InvalidTimingError("Pre-pulse delay too short")

        if (self.post_open_us - self.open_us / 2) < self.MIN_SWITCH_INTERVAL_US:
            raise InvalidTimingError("Post-pulse/reset delay too short")

        if abs(self.align_us) > self.LASER_PERIOD_US / 2:
            raise InvalidTimingError("Pulse train alignment nonsensically large")

        if abs(self.offset_on_us) > 2e-3:
            raise InvalidTimingError("Channel/channel ON switch delay longer than 2 ns")

        if abs(self.offset_off_us) > 2e-3:
            raise InvalidTimingError("Channel/channel OFF switch delay longer than 2 ns")


class PulsePickerTiming:
    """High-level experimentalist's interface for arming the pulse picker
    setup and specifying its timing parameters.

    Note that there is quite some potential for confusion due to overloaded
    terminology here. In normal experimentalist's usage, as well as this
    high-level interface, the term "pulse" refers to an optical laser pulse.
    A pulse picker is a device that selects from those pulses. To do that,
    the Pockels cell driver hardware needs to be triggered by a number of
    electronic pulses with certain delays between them, which is how the term
    is also used in the low-level delay generator driver.

    In a similar vein, the two pairs of high-voltage switches (high-side and
    low-side in an H-bridge configuration) are referred to as "on" and "off"
    in the labels and documentation of the pulse picker head, even though they
    do not correspond to optical bright/dark (which is the XOR of their states).

    Currently, only the BME_SG08p delay generator is supported, with its six
    channels connected as following to a BME pulse picker driver head:
    A: OFF A
    B: <unused>
    C: OFF B
    D: <unused>
    E: ON A
    F: ON B
    """

    def __init__(self, delay_gen, allow_long_pulses=False):
        """
        Create a new high-level interface for using the passed delay generator
        to drive a instance for driving a pulse picker head.

        :param delay_gen: The BME_SG08p instance to use. It will be configured
            for the pulse picker head, its outputs initially disabled. None for
            simulation mode.
        :param allow_long_pulses: Whether to allow (optical) pulses that are
            longer than sensible for calibrating single-pulse picking
            (2 * LASER_PERIOD_US).
        """

        self._delay_gen = delay_gen
        self._times = TimingParams(allow_long_pulses)

        if self._delay_gen:
            self._delay_gen.set_output_gates([
                OutputGateMode.gate_or,
                OutputGateMode.gate_or,
                OutputGateMode.direct])
            self._delay_gen.set_trigger(False, 0.0)

        self.disable()

    def disable(self):
        """Disable pulsing."""
        self._enabled = False
        self._update_pulses()

    def enable_gated(self, holdoff_us=0.0):
        """Enable pulsing, triggering one whenever the external gate input is
        signalled."""
        if self._delay_gen:
            self._delay_gen.set_trigger(True, holdoff_us)
        self._enabled = True
        self._update_pulses()

    def enable_free(self, min_period_us=10.0):
        """Enable pulsing in a free-running manner, where pulses are triggered
        whenever the laser sync trigger is asserted, but with a minimum period
        (hold-off/inhibit) of min_period_us."""
        if self._delay_gen:
            self._delay_gen.set_trigger(False, min_period_us)
        self._enabled = True
        self._update_pulses()

    # Timing accessors. The repetition should be abstracted away with a dash of
    # meta-programming magic.

    def get_offset_on_us(self):
        return self._times.offset_on_us

    def set_offset_on_us(self, value):
        new = copy.copy(self._times)
        new.offset_on_us = value
        new.ensure_valid()
        self._times = new
        self._update_pulses()

    def get_offset_off_us(self):
        return self._times.offset_off_us

    def set_offset_off_us(self, value):
        new = copy.copy(self._times)
        new.offset_off_us = value
        new.ensure_valid()
        self._times = new
        self._update_pulses()

    def get_pre_open_us(self):
        return self._times.pre_open_us

    def set_pre_open_us(self, value):
        new = copy.copy(self._times)
        new.pre_open_us = value
        new.ensure_valid()
        self._times = new
        self._update_pulses()

    def get_post_open_us(self):
        return self._times.post_open_us

    def set_post_open_us(self, value):
        new = copy.copy(self._times)
        new.post_open_us = value
        new.ensure_valid()
        self._times = new
        self._update_pulses()

    def get_open_us(self):
        return self._times.open_us

    def set_open_us(self, value):
        new = copy.copy(self._times)
        new.open_us = value
        new.ensure_valid()
        self._times = new
        self._update_pulses()

    def get_align_us(self):
        return self._times.align_us

    def set_align_us(self, value):
        new = copy.copy(self._times)
        new.align_us = value
        new.ensure_valid()
        self._times = new
        self._update_pulses()

    def ping():
        """Return true (for ARTIQ controller heartbeat mechanism)."""
        return True

    def _update_pulses(self):
        if not self._delay_gen:
            return

        if not self._enabled:
            self._delay_gen.set_pulse_parameters(
                [PulseParameters(False, 0.0, 0.0)] * 6)
            return

        self._times.ensure_valid()

        split_neg = lambda x: (-x, 0.0) if x < 0.0 else (0.0, x)
        s_a_off, s_b_off = split_neg(self._times.offset_off_us)
        s_a_on, s_b_on = split_neg(self._times.offset_on_us)

        open_at_us = self._times.pre_open_us + self._times.align_us

        self._delay_gen.set_pulse_parameters([
            PulseParameters(
                True,
                s_a_off,
                0.0),
            PulseParameters(
                True,
                s_a_off + self._times.pre_open_us + self._times.post_open_us,
                0.0),
            PulseParameters(
                True,
                s_b_off,
                0.0),
            PulseParameters(
                True,
                s_b_off + self._times.pre_open_us + self._times.post_open_us,
                0.0),
            PulseParameters(
                True,
                s_a_on + open_at_us - self._times.open_us / 2,
                0.0),
            PulseParameters(
                True,
                s_b_on + open_at_us + self._times.open_us / 2,
                0.0),
            ])
