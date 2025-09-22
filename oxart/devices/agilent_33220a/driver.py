from oxart.devices.streams import get_stream

import socket


class Agilent33220A:
    """Driver for Agilent 33220A AWGs"""

    def __init__(self, host, port, timeout=10):

        self._socket = socket.create_connection((host, port), timeout)

        # Adapter can be reached, so now ping device itself
        # assert self.ping(), "Agilent 33220A not responding to ping"

    def _read_line(self):
        # read more lines
        while len(self._lines) <= 1:
            chunk = self._socket.recv(4096)
            if not chunk:
                return None
            buf = self._lines[-1] + chunk.decode("utf-8", errors="ignore")
            self._lines = buf.split("\n")

        line = self._lines[0]
        self._lines = self._lines[1:]
        return line

    def _command(self, *command):
        print((" ".join(command) + "\n"))
        self._socket.sendall((" ".join(command).strip() + "\n").encode("utf-8"))

    def apply(self, function, frequency, V_pp, V_offset):
        self.set_function(function)
        self.set_frequency(frequency)
        self.set_v_pp(V_pp)
        self.set_v_offset(V_offset)
        self.on()

    def set_v_pp(self, V_pp):
        """Set the peak to peak Voltage in volts."""
        self._command("VOLTage", "{:f}".format(V_pp))

    def set_v_offset(self, V_offset):
        """Set the peak to peak Voltage in volts."""
        self._command("VOLTage:OFFSet", "{:f}".format(V_offset))

    def set_frequency(self, frequency):
        """Set the Frequency."""
        self._command("FREQuency", "{:f}".format(frequency))

    def set_function(self, function):
        """Set the voltage limit for channel in volts."""
        if function == "sin":
            function = "SINusoid"
        elif function == "square":
            function = "SQUare"
        elif function == "ramp":
            function = "RAMP"
        else:
            raise ValueError("Invalid function")

        self._command("FUNCtion", function)

    def on(self):
        self._command("OUTPut", "ON")

    def off(self):
        self._command("OUTPut", "OFF")

    def ping(self):
        ident = self.identify().lower().split(",")
        ident = [sub_str.strip() for sub_str in ident]
        return ident[0:2] == ["hewlett-packard", "33220A"]

    def reset(self):
        self._command("*RST")

    def close(self):
        self._socket.close()


if __name__ == "__main__":
    dev = Agilent33220A("10.255.6.26", 5025)
    # dev.reset()
    dev.set_function("square")
    dev.set_v_pp(5)
    dev.set_v_offset(2.5)
    dev.set_frequency(1e6)
    dev.on()
    dev.close()
