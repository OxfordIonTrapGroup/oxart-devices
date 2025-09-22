from oxart.devices.scpi_synth.driver import Synth as ScpiSynth


class Synth(ScpiSynth):
    """ Driver for Keysight 33500B Arbitrary Waveform Generators """
    def __init__(self, device):
        super().__init__(device)

    def trigger(self):
        """ Generates a device trigger event """
        self.stream.write("*TRG\n".encode())
