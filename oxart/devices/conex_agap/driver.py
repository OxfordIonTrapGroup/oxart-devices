import logging
import serial
from enum import Enum
import time

logger = logging.getLogger(__name__)

StateType = Enum(
    "StateType",
    [
        "NotReferenced",
        "Configuration",
        "Moving",
        "Stepping",
        "Ready",
        "Disable",
        "Other",
    ],
)


class ConexMirror:
    """Driver for Newport CONEX motor controller."""

    def __init__(self, id, serial_addr):
        self.port = serial.Serial(serial_addr,
                                  baudrate=921600,
                                  timeout=0.1,
                                  write_timeout=0.1)
        self.id = id
        s = self.get_status()
        if s != StateType.Ready:
            raise Exception("Controller in unexpected state {}".format(s))

    def close(self):
        """Close the serial port."""
        self.port.close()

    def _send_command(self, cmd):
        command = self.id + cmd + "\r\n"
        self.port.write(command.encode())

    def _read_line(self):
        """Read a CR terminated line. Returns '' on timeout"""
        s = ""
        while len(s) == 0 or s[-1] != "\r":
            c = self.port.read().decode()
            if c == "":  # Timeout
                break
            s += c
            return s

    def home(self):
        """Go to home position - required after reset of controller before any other
        operation. If blocking, do not return until homing complete"""
        self.set_position("U", 0)
        self.set_position("V", 0)

    def set_position(self, ax, pos, absolute=True, blocking=True):
        """Go to a position. If blocking, do no return until the stage has stopped
        moving"""
        if absolute:
            self._send_command("PA{}{}".format(ax, pos))
        else:
            self._send_command("PR{}{}".format(ax, pos))

        if blocking:
            while True:
                time.sleep(10e-3)
                s = self.get_status()
                if s == StateType.Ready:
                    return

    def stop(self):
        """Stop motion"""
        self._send_command("ST")

    def reset(self):
        """hardware Reset"""
        self._send_command("RS")

    def get_position(self, ax):
        """Returns the current position. In MOVING state, the position changes
        according to the calculation of the motion profiler. In READY state, the
        setpoint position is equal to the target position.
        """
        self._send_command("TP{}".format(ax))
        line = self._read_line()
        pos_str = line.strip()[4:]
        try:
            pos = float(pos_str)
        except ValueError:
            raise ValueError("Could not interpret response '{}'".format(pos_str))
        return pos

    def get_status(self):
        """Return the status code of the controller"""
        self._send_command("TS")
        line = self._read_line().strip()
        state_code = line[7:9].lower()
        st = StateType.Other
        if state_code in ["0a", "0b", "0c", "0d", "0e", "0f", "10"]:
            st = StateType.NotReferenced
        elif state_code == "14":
            st = StateType.Configuration
        elif state_code == "28":
            st = StateType.Moving
        elif state_code == "29":
            st = StateType.Stepping
        elif state_code in ["32", "33", "34", "35", "36"]:
            st = StateType.Ready
        elif state_code in ["3c", "3d"]:
            st = StateType.Disable
        elif state_code == "46":
            st = StateType.Jogging
        return st
