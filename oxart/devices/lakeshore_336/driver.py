from oxart.devices.streams import get_stream


class LakeShore336:
    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def ping(self):
        idn = self.identify()
        return bool(idn)

    def _send_cmd(self, msg):
        cmd = msg + "\n"
        self.stream.write(cmd.encode())

    def _read_line(self):
        return self.stream.readline().decode()

    def identify(self):
        self._send_cmd("*IDN?")
        return self._read_line()

    def get_temp(self, input="A"):
        """ Returns the temperature of an input channel as a float in Kelin
        : param input: either "A" or "B"
        """
        self._send_cmd("KRDG? {}".format(input))
        return float(self._read_line())

    def close(self):
        self.stream.close()
