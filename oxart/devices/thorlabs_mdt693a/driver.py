import logging
import serial
import re

logger = logging.getLogger(__name__)


class PiezoController:
    """Driver for Thorlabs MDT693A 3-channel open-loop piezo controller.
    NB The knobs on the piezo controller must be set to 0 voltage (i.e. turned
    fully counter-clockwise) before using the driver to set the voltages.
    """

    def __init__(self, device):
        self.dev = serial.serial_for_url("socket://{}:9001".format(device),
                                         baudrate=115200,
                                         timeout=1)
        assert self.ping()

    def close(self):
        """Close the serial port."""
        self.dev.close()

    def ping(self):
        self._send_cmd("I")
        return bool(self._read_ping())

    def _send_cmd(self, msg):
        cmd = msg + "\r"
        self.dev.write(cmd.encode())

    def _read_ping(self):
        return self.dev.readline().decode()

    def _read_line(self):
        """Send a command, and return the output of the command as a string"""
        s = self.dev.readline().decode()
        a1 = re.search(r'\[(.*)\]', s)
        a2 = re.search(r'\*([0-9\.]+\Z)', s)
        while a1 is None and a2 is None and s != '':
            s = self.dev.readline().decode()
            a1 = re.search(r'\[(.*)\]', s)
            a2 = re.search(r'\*([0-9\.]+\Z)', s)
        if a1 is not None:
            return a1.group(1)
        elif a2 is not None:
            return a2.group(1)
        else:
            raise Exception('No information returned from command')

    def read_voltage(self, ch):
        msg = ch + "R?"
        self._send_cmd(msg)
        reply = self._read_line()
        voltage = reply
        return voltage

    def set_voltage(self, ch, voltage):
        msg = "%sV" % (ch) + "{:.3f}".format(voltage)
        self._send_cmd(msg)
