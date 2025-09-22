from oxart.devices.scpi_device.driver import SCPIDevice
import logging

logger = logging.getLogger(__name__)


class SCPIAWG(SCPIDevice):
    def set_waveform(self, waveform, channel=1):
        waveforms = ("SIN", "SQU", "TRI", "RAMP", "PULS", "PSRB", "NOIS", "ARB", "DC")
        if waveform not in waveforms:
            raise ValueError("Waveform '{}' not recognised".format(waveform))
        self.send("SOUR{}:FUNC {}".format(channel, waveform))

    def set_frequency(self, frequency, channel=1):
        """Set frequency in Hz"""
        self.send("SOUR{}:FREQ {}".format(channel, frequency))

    def set_amplitude(self, power, channel=1):
        """Set output amplitude"""
        self.send("SOUR{}:VOLT {}".format(channel, power))

    def set_amplitude_dbm(self, power, channel=1):
        """Set output amplitude in dBm"""
        self.send("SOUR{}:VOLT {} DBM".format(channel, power))

    def set_output(self, enable, channel=1):
        if enable:
            en_str = "ON"
        else:
            en_str = "OFF"
        self.send("OUTP{} {}".format(channel, en_str))
