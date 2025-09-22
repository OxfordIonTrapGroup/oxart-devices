import pyvisa  # pip install -U pyvisa-py
import numpy as np
import logging

logger = logging.getLogger(__name__)


def list_resources():
    rm = pyvisa.ResourceManager('@py')
    return rm.list_resources()


class MSOX3104G:
    """Keysight InfiniiVision MSOX3104G driver"""

    def __init__(self, address: str):
        self._rm = pyvisa.ResourceManager('@py')

        self.dev = self._rm.open_resource(address)
        self.dev.timeout = 15000 * 4
        self.dev.clear()

        # These attributes are assigned in :meth:`setup_acquisition`.
        self.x_increment = None
        self.y_increment = None
        self.x_origin = None
        self.y_origin = None
        self.y_reference = None

        print('Oscilloscope ready: %s' % (address))

    def setup_trigger_from_edge(self,
                                mode: str,
                                source: int,
                                level: float = 20.0,
                                slope_positive: bool = True):
        self.dev.write(":TRIGger:MODE EDGE")
        self.dev.write(":TRIGger:SWEep NORMal")
        self.dev.write(f":TRIGger:EDGE:SOURce CHANnel{source}")
        self.dev.write(f":TRIGger:EDGE:LEVel {level}")
        if slope_positive:
            self.dev.write(":TRIGger:EDGE:SLOPe POSitive")
        else:
            self.dev.write(":TRIGger:EDGE:SLOPe NEGative")

    def digitize(self, channel: int):
        self.dev.write(f":DIGitize CHANnel{channel}")

    def setup_acquisition(self, channel: int):
        self.dev.write(":WAVeform:POINts:MODE MAX")
        self.dev.write(":WAVeform:FORMat WORD")
        self.dev.write(":WAVeform:BYTeorder LSBFirst")
        self.dev.write(":WAVeform:UNSigned 0")

        self.dev.write(f":WAVeform:SOURce CHANnel{channel}")
        self.dev.write(":WAVeform:POINts MAX")

        ACQ_TYPE = str(self.dev.query(":ACQuire:TYPE?")).strip("\n")
        if ACQ_TYPE == "AVER" or ACQ_TYPE == "HRES":
            self.dev.write(":WAVeform:POINts:MODE NORMal")
        else:
            self.dev.write(":WAVeform:POINts:MODE RAW")

        preamble_string = self.dev.query(":WAVeform:PREamble?")
        (_, _, _, _, x_increment, x_origin, _, y_increment, y_origin, y_reference) = \
            preamble_string.split(",")

        self.x_increment = float(x_increment)
        self.y_increment = float(y_increment)
        self.x_origin = float(x_origin)
        self.y_origin = float(y_origin)
        self.y_reference = float(y_reference)

    def acquire_waveform(self, channel: int):
        if self.x_increment is None:
            logger.error("Forgot to call setup_acquisition()?")
        values = self.dev.query_binary_values(
            f":WAVeform:SOURce CHANnel{channel} ;DATA?", "h", False)

        times = np.empty(len(values))
        voltages = np.empty(len(values))
        for i, val in enumerate(values):
            times[i] = self.x_origin + (i * self.x_increment)
            voltages[i] = ((val - self.y_reference) * self.y_increment) + self.y_origin
        return times, voltages

    def close(self):
        self._rm.close()

    def ping(self):
        return True
