import serial

class Sumitomo:
    """
    Driver for the sumitomo cryo compressor
    """
    def __init__(self, device):
        self.dev = serial.serial_for_url("socket://{}:9001".format(device),
                                            timeout=1)
        assert self.ping()

    def close(self):
        """Close the serial port."""
        self.dev.close()

    def ping(self):
        self._send_cmd("ID1D629")
        return bool(self._read_line())

    def _send_cmd(self, msg):
        cmd = "$" + msg + "\r"
        self.dev.write(cmd.encode())

    def _read_line(self):
        return self.dev.readline().decode()

    def switch_on(self):
        """
        Switches on the cryostat
        """
        cmd = "ON177CF"
        self._send_cmd(cmd)

    def switch_off(self):
        """
        Switches off the cryostat
        """
        cmd = "OFF9188"
        self._send_cmd(cmd)
