from oxart.devices.streams import get_stream

class Turbo:

    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def ping(self):
        self._send_cmd("?S902")
        return bool(self._read())

    def _send_cmd(self, msg):
        cmd = msg + "\r"
        self.stream.write(cmd.encode())

    def _read(self):
        return self.stream.read(20).decode()

    def get_pressure(self):
        """ Returns the temperature of an input channel as a float in Kelin
        : param input: either "A" or "B"
        """
        self._send_cmd("?V913")
        reply = self._read()
        pressure = float(reply.split(" ")[1].split(";")[0])/100
        return pressure

    def switch_on(self):
        cmd = "!C904 1"
        self._send_cmd(cmd)

    def switch_off(self):
        cmd = "!C904 0"
        self._send_cmd(cmd)

    def close(self):
        self.stream.close()
