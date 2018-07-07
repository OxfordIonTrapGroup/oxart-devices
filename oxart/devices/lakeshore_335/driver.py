""" Driver for Lake Shore Cryogenics Model 335 Temperature controllers """

from oxart.streams import Ethernet


class LakeShore335:

    def __init__(self, addr, port=1234):
        self.sock = Ethernet(addr, port)

    def identify(self):
        return self.sock.write("*IDN?\n".encode())

    def get_temp(self):
        return self.sock.write("KRDG?\n".encode())

    def ping(self):
        return bool(self.get_version())
