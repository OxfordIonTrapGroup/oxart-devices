from oxart.devices.streams import get_stream


class Synth:
    """ Generic driver for SCPI-compliant frequency synthesisers """
    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def identify(self):
        """ Return a device ID string. """
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def ping(self):
        return bool(self.identify().lower().split(","))

    def set_freq(self, freq):
        """ Program the device to a frequency in Hz. """
        self.stream.write("FREQ {} HZ\n".format(freq).encode())

    def get_freq(self):
        """ Returns the current frequency setting. """
        self.stream.write("FREQ?\n".encode())
        return self.stream.readline().decode()

    def set_power(self, power):
        self.stream.write("POW {} DBM\n".format(power).encode())

    def get_power(self):
        self.stream.write("POW?\n".encode())
        return float(self.stream.readline().decode())

    def set_amplitude(self, volts):
        self.stream.write("VOLT {}\n".format(volts).encode())

    def set_rf_on(self, enabled):
        self.stream.write("OUTP {:d}\n".format(int(enabled)).encode())

    def get_rf_on(self):
        self.stream.write("OUTP?\n".encode())
        return bool(int(self.stream.readline().decode()))
