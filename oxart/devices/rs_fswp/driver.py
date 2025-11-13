# ######################
# ###### NOTE!!!! ######
# ######################

# Requires rsfsw, PyVisa and pyvisa-py packages

# For examples and documentation, see
# https://rohde-schwarz.github.io/RsFsw_PythonDocumentation/index.html

from RsFsw import RsFsw, LoggingMode, enums, repcap
from logging import getLogger
from typing import Tuple, Optional
import os

logger = getLogger()


class RS_FSWP:

    def __init__(self, ip="169.254.147.5", prefix="TCPIP", suffix="INSTR"):
        self.ip = ip
        self.prefix = prefix
        self.suffix = suffix

    def ping(self):
        response = os.system(f"ping {self.ip}")
        print(response)

    def initialise_connection(self):
        # A good practice is to check for the installed version
        RsFsw.assert_minimum_version("4.90.0")

        # Open the session with the Spectrum Analyser
        try:
            address = "::".join([self.prefix, self.ip, self.suffix])
            self.fsw = RsFsw(address)
            logger.info("Connected to Device")
        except Exception:
            print("Connection timed out.")

    def close(self):
        self.fsw.close()

    def prep_for_scan(self):
        # Don't print commands to the console with the logger
        self.fsw.utilities.logger.mode = LoggingMode.On
        self.fsw.utilities.logger.log_to_console = False

        # # Driver's instrument status checking ( SYST:ERR? ) after each command
        # (default value is true):
        self.fsw.utilities.instrument_status_checking = True

        # # Device display updates after every run
        self.fsw.system.display.update.set(True)

    def set_continuous(self, continuous: bool = True):
        """Choose whether to run a continuous scan or take one scan at a time.

        :param continuous: Whether to make the scan continuous or not
        """
        self.fsw.initiate.continuous.set(continuous)

    def set_scan_start_and_end(self, scan_start: float, scan_end: float):
        """Set the start and end fequencies of a scan.

        :param scan_start: Scan start frequency in Hz.
        :param scan_end: Scan end frequency in Hz.
        """

        self.fsw.sense.frequency.start.set(scan_start)
        self.fsw.sense.frequency.stop.set(scan_end)

    def get_scan_start_and_end(self) -> Tuple[float, float]:
        """Get the start and end frequencies of a scan in Hz.

        :return: Tuple (start_frequency, end_frequency) in Hz.
        """
        start_frequency = self.fsw.sense.frequency.start.get()
        end_frequency = self.fsw.sense.frequency.stop.get()
        return start_frequency, end_frequency

    def set_power_reference_level(self, reference_level: float):
        """Set the power (y-axis) reference level.

        :param reference_level: Reference level in dBm.
        """
        self.fsw.display.window.trace.y.scale.refLevel.set(reference_level)

    def get_power_reference_level(self) -> float:
        """Get the power (y-axis) reference level.

        :return: Reference level in dBm.
        """
        return self.fsw.display.window.trace.y.scale.refLevel.get()

    def set_resolution_bandwidth(self, bandwidth: float):
        """Set the resolution bandwidth (RBW).

        :param bandwidth: Resolution bandwidth in Hz.
        """
        self.fsw.sense.bandwidth.resolution.set(bandwidth)

    def set_auto_resolution_bandwidth(self, state: bool = True):
        """Whether to let the instrument set the RBW automatically.

        :param state: If True, set RBW to auto.
        """
        self.fsw.sense.bandwidth.resolution.auto.set(state)

    def get_resolution_bandwidth(self) -> float:
        """Get current resolution bandwidth (RBW)

        :return: Resolution bandwidth in dBm.
        """
        return self.fsw.sense.bandwidth.resolution.get()

    def set_num_points(self, num_points: int):
        """Set the number of points per scan sweep."""
        self.fsw.sense.sweep.points.set(num_points)

    def get_num_points(self) -> int:
        """Get the current number of points per scan sweep.

        :return: Number of points.
        """
        return self.fsw.sense.sweep.points.get()

    def set_sweep_time(self, sweep_time: float):
        """Set the time for a single sweep.

        :param sweep_time: Sweep time in s.
        """
        self.fsw.sense.sweep.time.set(sweep_time)

    def set_auto_sweep_time(self, state: bool = True):
        """Whether to let the instrument automatically.

        :param state: If True, set sweep time to auto.
        """
        self.fsw.sense.sweep.time.auto.set(state)

    def get_sweep_time(self) -> float:
        """Get the current sweep time.

        :return: Sweep time in s.
        """
        return self.fsw.sense.sweep.time.get()

    def set_marker(self, trace_number: int = 1, window=None, marker=None):
        """Set a marker at the desired trace. By default, sets marker 1 onto trace 1
        in window 1.

        :param trace_number: The trace on which to set the marker.
        :param window: Optionally, the window onto which to set the marker. If passed,
            of the form repcap.Window.Nr<n>
        :param marker: Optionally, the marker that is to be set. If passed, of the form
            repcap.Marker.Nr<n>
        :return: Tuple containing the window onto which the number has been set and the
            marker.
        """
        if window is None:
            window = repcap.Window.Nr1
        if marker is None:
            marker = repcap.Marker.Nr1
        self.fsw.calculate.marker.trace.set(trace_number, window, marker)
        return window, marker

    def set_marker_at_peak(self, trace_number: int = 1, window=None, marker=None):
        """Set a marker to follow the peak frequency of the desired trace. By
        default, sets marker 1 onto trace 1 in window 1.

        :param trace_number: The trace on which to set the marker.
        :param window: Optionally, the window onto which to set the marker. If passed,
            of the form repcap.Window.Nr<n>
        :param marker: Optionally, the marker that is to be set. If passed, of the form
            repcap.Marker.Nr<n>
        :return: Tuple containing the window onto which the number has been set and the
            marker.
        """
        window, marker = self.set_marker(trace_number, window, marker)
        self.fsw.calculate.marker.maximum.peak.set(repcap.Window.Nr1, repcap.Marker.Nr1)
        return window, marker

    def get_marker_frequency(self, window, marker) -> float:
        """Get frequency at which the marker is set. This is useful if the marker has
        been set to follow the peak of a trace.

        :param window: The window onto which the marker is set, of the form
            repcap.Window.Nr<n>
        :param marker: The marker, of the form repcap.Marker.Nr<n>
        :return: Marker frequency in Hz.
        """
        return self.fsw.calculate.marker.x.get(window, marker)

    def get_marker_amplitude(self, window, marker) -> float:
        """Get the amplitude at the marker's frequency.

        :param window: The window onto which the marker is set, of the form
            repcap.Window.Nr<n>
        :param marker: The marker, of the form repcap.Marker.Nr<n>
        :return: Marker amplitude in dBm.
        """
        return self.fsw.calculate.marker.y.get(window, marker)

    def setup_scan(
        self,
        min_freq_Hz: float,
        max_freq_Hz: float,
        resolution_Hz: Optional[float] = None,
        ref_level_dBm: float = -20,
        num_points: int = 1001,
    ):
        """Set up a single scan.

        Params:
        :min_freq_Hz: Scan minimum frequency in Hz
        :max_freq_Hz: Scan maximum frequency in Hz
        :resolution_Hz: The Resolution Bandwidth (RBW) at each scan point in Hz
                        (essentially, the bandwidth of the filter applied
                        at each point)
        :ref_level_dB: The scan reference level in dB
        :num_points: Number of points in scan
        """
        self.min_freq_Hz = min_freq_Hz
        self.max_freq_Hz = max_freq_Hz
        self.resolution_Hz = resolution_Hz
        self.ref_level_dBm = ref_level_dBm
        self.num_points = num_points

        self.prep_for_scan()

        # # Only take one sweep at a time
        self.set_continuous(False)

        # # Set start and end frequencies
        self.set_scan_start_and_end(self.min_freq_Hz, self.max_freq_Hz)

        # # Set power reference level
        self.set_power_reference_level(self.ref_level_dBm)

        window = repcap.Window.Nr1

        # # Make one trace, set it to measure AVERage mode
        self.fsw.display.window.subwindow.trace.mode.set(
            enums.TraceModeF.AVERage,
            window,
            repcap.SubWindow.Default,
            repcap.Trace.Tr1,
        )

        # # Set resolution bandwidth
        if resolution_Hz is None:
            self.set_auto_resolution_bandwidth()
        else:
            self.set_resolution_bandwidth(self.resolution_Hz)

        # # Set number of sweep points, and sweep time to auto (min time)
        self.set_num_points(self.num_points)
        self.set_auto_sweep_time()

    def get_scan_params(self):
        """Return the currently set scan parameters.

        :returns: Tuple[min_frequency_Hz, max_frequency_Hz, resolution_Hz, ref_level_dB,
            num_points]
        """

        min_freq_Hz, max_freq_Hz = self.get_scan_start_and_end()
        resolution_Hz = self.get_resolution_bandwidth()
        ref_level_dB = self.get_power_reference_level()
        num_points = self.get_num_points()
        return min_freq_Hz, max_freq_Hz, resolution_Hz, ref_level_dB, num_points

    def scan_and_get_peak(self) -> Tuple[float, float]:
        """Runs a single scan and return the frequency and amplitude of the peak
        frequency in the scan.

        :return: A tuple with the peak frequency in Hz and amplitude in dBm.
        """
        # Start the trace
        self.fsw.initiate.immediate_with_opc(3000)

        window, marker = self.set_marker_at_peak()

        frequency = self.get_marker_frequency(window, marker)

        ampl = self.get_marker_amplitude(window, marker)

        logger.info(f"Peak: {frequency} Hz, {ampl} dBm")

        return frequency, ampl
