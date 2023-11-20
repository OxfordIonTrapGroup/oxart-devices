import logging
import serial

logger = logging.getLogger(__name__)


class PiezoController:
    """Driver for Thorlabs MDT693A 3-channel open-loop piezo controller.
    NB The knobs on the piezo controller must be set to 0 voltage (i.e. turned
    fully counter-clockwise) before using the driver to set the voltages.
    """

    def __init__(self, device):
        self.dev = serial.serial_for_url("socket://{}:9001".format(device), timeout=1)
        assert self.ping()

    def close(self):
        """Close the serial port."""
        self.dev.close()

    def ping(self):
        self._send_cmd("I")
        return bool(self._read_line())

    def _send_cmd(self, msg):
        cmd = msg + "\r"
        self.dev.write(cmd.encode())

    def _read_line(self):
        return self.dev.readline().decode()

    def read_voltage(self, ch):
        msg = ch + "R??"
        self._send_cmd(msg)
        reply = self._read_line()
        voltage = reply

        return voltage

    def set_voltage(self, ch, voltage):
        msg = ch + "V" + str(voltage)
        self._send_cmd(msg)
