import time
import serial
import logging
import asyncio
import numpy as np
from .pirate_dac import PirateDac

logger = logging.getLogger(__name__)


N_CHANNELS = 4

class HOA2Dac:
    def __init__(self, serial_name):
        """serial_name : serial port name

        Output assignment:
        ch 0: centre inner electrodes (Q19, Q20)
        ch 1: far inner electrodes (Q09-Q18, Q21-Q30)
        ch 2: outer electrode 1 (Q39)
        ch 3: outer electrode 2 (Q40)
        """
        self.dac = PirateDac(serial_name)

        self.y_comp = 0
        self.z_comp = 0
        self.sr_trap_freq = 1e6

    def write_raw_voltages(self, voltages):
        assert(len(voltages)==N_CHANNELS)
        for ch, v in enumerate(voltages):
            self.dac.set_channel(v, ch=ch, update=False)
        self.dac.pulse_ldac()

    def read_raw_voltages(self):
        return [self.dac.read_channel(ch) for ch in range(4)]

    def update_voltages(self):
        voltages = [0]*4

        # Axial trapping term
        freq_scaling = (88/170) * (self.sr_trap_freq/700e3)**2
        voltages[0] += -1 * freq_scaling
        voltages[1] += +1 * freq_scaling
        voltages[2] += -0.445 * freq_scaling
        voltages[3] += -0.442 * freq_scaling

        # Y compensation term
        voltages[2] += -0.987 * self.y_comp/1000
        voltages[3] += +0.985 * self.y_comp/1000

        # Z compensation term
        voltages[2] += -0.777 * self.z_comp/1000
        voltages[3] += -0.775 * self.z_comp/1000

        logger.debug("Setting voltages :", voltages)
        self.write_raw_voltages(voltages)

    def set_z_compensation(self, z_comp, update=True):
        """Sets the z (normal to trap plane) compensation voltage in V/m.
        If update=True the DAC voltages are updated immediately."""
        self.z_comp = z_comp
        if update:
            self.update_voltages()

    def set_y_compensation(self, y_comp, update=True):
        """Sets the y (transverse, in trap plane) compensation voltage in V/m.
        If update=True the DAC voltages are updated immediately."""
        self.y_comp = y_comp
        if update:
            self.update_voltages()

    def set_trap_frequency(self, freq, update=True):
        """Set the axial trap frequency for Strontium, in Hz.
        If update=True the DAC voltages are updated immediately."""
        self.sr_trap_freq = freq
        if update:
            self.update_voltages()

    def ping(self):
        # TODO: write a proper ping that checks if the PirateDac is alive,
        # without toggling any gates on the DAC itself
        return True

