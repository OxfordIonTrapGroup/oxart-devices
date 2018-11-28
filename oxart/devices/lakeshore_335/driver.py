""" Driver for Lake Shore Cryogenics Model 335 Temperature controllers """

from oxart.devices.streams import get_stream


class LakeShore335:

    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def get_temp(self, input="A"):
        """ Returns the temperature of an input channel as a float in Kelin
        : param input: either "A" or "B"
        """
        self.stream.write("KRDG? {}\n".format(input).encode())
        return float(self.stream.readline())

    def ping(self):
        idn = self.identify().split(',')
        return idn[0:2] == ['LSCI', 'MODEL335']

    def close(self):
        self.stream.close()
