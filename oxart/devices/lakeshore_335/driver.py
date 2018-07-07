""" Driver for Lake Shore Cryogenics Model 335 Temperature controllers """

from oxart.devices.streams import Ethernet


class LakeShore335:

    def __init__(self, addr, port=1234):
        self.sock = Ethernet(addr, port)

    def identify(self):
        self.sock.write("*IDN?\n".encode())
        return self.sock.readline().decode()

    def get_temp(self, input="A"):
        """ Returns the temperature of an input channel as a float in Kelin
        : param input: either "A" or "B"
        """
        self.sock.write("KRDG? {}\n".format(input).encode())
        return float(self.sock.readline())

    def ping(self):
        idn = self.identify().split(',')
        return idn[0:2] == ['LSCI', 'MODEL335']
