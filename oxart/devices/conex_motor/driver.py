import logging
import serial
import sys
import asyncio
from enum import Enum
import time

logger = logging.getLogger(__name__)

StateType = Enum("StateType",
                 ["NotReferenced", "Homing", "Moving", "Ready", "Disable", "Other"])


class Conex:
    """Driver for Newport CONEX motor controller."""

    def __init__(self, serial_addr, position_limit=None, auto_home=True):
        self.port = serial.Serial(serial_addr,
                                  baudrate=921600,
                                  timeout=0.1,
                                  write_timeout=0.1)

        if auto_home:
            s = self.get_status()
            if s == StateType.NotReferenced:
                self.home()

            # At this point we should be in the READY state
            s = self.get_status()
            if s != StateType.Ready:
                raise Exception("Controller in unexpected state {}".format(s))

        if position_limit:
            self.set_upper_limit(position_limit)

    def close(self):
        """Close the serial port."""
        self.port.close()

    def _send_command(self, cmd):
        try:
            self.port.write(("1" + cmd + "\r\n").encode())
        except serial.SerialTimeoutException:
            logger.exception("Serial write timeout: Force exit")
            # This is hacky but makes the server exit
            asyncio.get_event_loop().call_soon(sys.exit, 42)
            raise

    def _read_line(self):
        """Read a CR terminated line. Returns '' on timeout"""
        s = ''
        while len(s) == 0 or s[-1] != '\r':
            c = self.port.read().decode()
            if c == '':  # Timeout
                break
            s += c
        return s

    def home(self, blocking=True):
        """Go to home position - required after reset of controller before any
        other operation. If blocking, do not return until homing complete"""
        self._send_command("OR")

        if blocking:
            while True:
                time.sleep(0.1)
                s = self.get_status()
                if s == StateType.Ready:
                    return
                elif s != StateType.Homing:
                    raise Exception("State is not homing ({})".format(s))

    def set_position(self, pos, blocking=True):
        """Go to an absolute position. If blocking, do no return until the stage
        has stopped moving"""
        self._send_command("PA{}".format(pos))
        if blocking:
            while True:
                time.sleep(10e-3)
                s = self.get_status()
                if s == StateType.Ready:
                    return
                elif s != StateType.Moving:
                    raise Exception("State is not moving ({})".format(s))

    def stop(self):
        """Stop motion"""
        self._send_command("ST")

    def get_position(self):
        """Returns the current setpoint position.

        In MOVING state, the set-point position changes according to the
        calculation of the motion profiler. In READY state, the setpoint
        position is equal to the target position.
        """
        self._send_command("TH")
        line = self._read_line()
        pos_str = line.strip()[3:]
        try:
            pos = float(pos_str)
        except ValueError:
            raise ValueError("Could not interpret response '{}'".format(pos_str))
        return pos

    def set_upper_limit(self, limit):
        """Set upper limit on stage position (=extension)"""
        self._send_command("SR{}".format(limit))

    def get_status(self):
        """Return the status code of the controller"""
        self._send_command("TS")
        line = self._read_line().strip()
        state_code = line[7:9].lower()
        st = StateType.Other
        if state_code in ["0a", "0b", "0c", "0d", "0e", "0f", "10"]:
            st = StateType.NotReferenced
        elif state_code == "1e":
            st = StateType.Homing
        elif state_code == "28":
            st = StateType.Moving
        elif state_code in ["32", "33", "34", "36"]:
            st = StateType.Ready
        elif state_code in ["3c", "3d", "3e", "3f"]:
            st = StateType.Disable
        return st

    def ping(self):
        return True
