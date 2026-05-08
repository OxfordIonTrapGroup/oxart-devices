"""Driver for GM08 Hirsch Gaussmeter.

Requires the driver DLL file from Hirsch to be installed locally, with location
specified by the $GM08_DLL_PATH environment variable. Searches in the default installer
location if none specified.
"""
import time
import logging
from oxart.devices.hirst_gaussmeter.gm0 import *
from enum import Enum

logger = logging.getLogger()


class Unit(Enum):
    TESLA = 0
    GAUSS = 1
    AMPERE_PER_METRE = 2
    OERSTED = 3


class Mode(Enum):
    DC = 0
    DC_PEAK = 1
    AC = 2
    AC_MAX = 3
    AC_PEAK = 4
    HOLD = 5


class GaussMeter:

    def __init__(self, device):
        self.handle = gm0_newgm(device, 1)

    def __del__(self):
        self.close()

    def connect(self):
        logger.info("Initiating connection to GM...")
        gm0_startconnect(self.handle)

        # GM08 is slow at connecting.
        while gm0_getconnect(self.handle) == 0:
            time.sleep(1)

        assert self.ping()
        logger.info("Connection established.")

        self.default()

        logger.info("Probe offset: %s", gm0_getprobeoffset(self.handle))

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def get_unit(self):
        unit = gm0_getunits(self.handle)
        return Unit(unit)

    def set_unit(self, unit: Unit):
        logger.info("Setting unit: %s (code %s)", unit.name, unit.value)
        return gm0_setunits(self.handle, unit.value)

    def get_mode(self):
        mode = gm0_getmode(self.handle)
        return Mode(mode)

    def set_mode(self, mode):
        logger.info("Setting mode: %s (code %s)", mode.name, mode.value)
        gm0_setmode(self.handle, mode.value)

    def set_range(self, rng):
        gm0_setrange(self.handle, rng)

    def autorange(self):
        logger.info("Setting autorange")
        self.set_range(4)

    def has_new_data(self):
        return gm0_isnewdata(self.handle)

    def get_latest_measurement(self):
        """Get the latest device measurement (Tesla)"""

        value = gm0_getvalue(self.handle)
        unit = self.get_unit()

        # There seems to be somewhat arbitrary conversion factors in
        # what is sent over USB + internal converion in the Hirst library
        # The conversions depend on both the range and the unit chosen.
        # although in our testing within a few ranges the error appears to
        # only depend on the unit.
        if unit == Unit.TESLA:
            scale = 1e-5
        elif unit == Unit.GAUSS:
            # This conversion has only been tested quickly
            scale = 1e-9
        else:
            logger.warning("The conversion for this unit is untested, "
                           "value may be powers of 10 off")
            scale = 1
        return value * scale

    def ping(self):
        """Perform a ping by querying the connected status 1 = connected 0 =
        connecting <0 = error."""
        return gm0_getconnect(self.handle) == 1

    def get_serial_no(self):
        # return a tuple of probe serial no and meter serial no.
        return (gm0_getprobesn(self.handle), gm0_getmetersn(self.handle))

    def default(self):
        self.set_unit(Unit.TESLA)
        self.set_mode(Mode.DC)
        self.autorange()

    def close(self):
        return gm0_killgm(self.handle)

    def autozero(self):
        gm0_doaz(self.handle)
        return gm0_resetnull(self.handle)
