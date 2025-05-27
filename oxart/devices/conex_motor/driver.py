import logging
import serial
import sys
import asyncio
from enum import Enum
import time

logger = logging.getLogger(__name__)

StateType = Enum(
    "StateType",
    ["NotReferenced", "Homing", "Moving", "Ready", "Disable", "Configuartion", "Other"])

#: For now, we only use channel 1 of the controller (motor controllers are
#: single-channel anyway).
CHANNEL_IDX = 1


class ConexError(RuntimeError):

    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"Hardware reported error: {message} (code: {code})")


class Conex:
    """Driver for Newport CONEX motor controller."""

    def __init__(self, serial_addr, position_limit=None, auto_home=True):
        self.port = serial.serial_for_url(serial_addr,
                                          baudrate=921600,
                                          timeout=10.0,
                                          write_timeout=10.0)

        if auto_home:
            self.reset()
            s = self.get_status()
            if s == StateType.NotReferenced:
                self.home()

            # At this point we should be ihomehomn the READY state
            s = self.get_status()
            if s != StateType.Ready:
                raise Exception("Controller in unexpected state {}".format(s))

        # Can't write limits when not referenced, so store for later if stage is not homed
        # yet. This is slightly unsatisfactory, as we duplicate hardware state, but we want
        # to make it as hard as possible for the user accidentally to end up putting the stage
        # to a position larger than the specified position_limit even if they manually need to
        # home() first.
        self._cached_lower_limit = 0
        if position_limit is None:
            # KLUDGE: Hard-coded limit for the linear micrometer motors we are using;
            # could query SU and multiply by 2147000000 as per the docs to make general.
            self._cached_upper_limit = 12
        else:
            self._cached_upper_limit = position_limit

        s = self.get_status()
        if s == StateType.Configuartion:
            logger.warning(
                "Controller was left behind in configuration mode; leaving it.")
            self._execute_checked_command("PW0", delay_before_status_read=10.0)

        s = self.get_status()
        if s == StateType.NotReferenced:
            logger.warning(
                "Skipping application of limits, as stage not referenced (homed); " +
                "will be applied once home[_to_current]() is called.")
        elif s == StateType.Ready:
            self.set_upper_limit(self._cached_upper_limit)
        else:
            raise Exception("Controller in unexpected state {}".format(s))

    def close(self):
        """Close the serial port."""
        self.port.close()

    def _send_command(self, cmd):
        logger.info("Sending hardware command: '%s'", cmd)
        try:
            self.port.write(("1" + cmd + "\r\n").encode())
        except serial.SerialTimeoutException:
            logger.exception("Serial write timeout: Force exit")
            # This is hacky but makes the server exit
            asyncio.get_event_loop().call_soon(sys.exit, 42)
            raise

    def _read_line(self):
        """Read a CR terminated line. Returns '' on timeout"""
        s = ""
        while not s or s[-1] != "\n":
            c = self.port.read().decode()
            if not c:  # Timeout
                logger.warning(r"Serial port read timeout while waiting for \n")
                break
            s += c
        if len(s) < 2 or s[-2:] != "\r\n":
            logger.warning(r"Expected line terminated with CRLF (\r\n), got: '%s'", s)
        else:
            # Strip \r\n
            s = s[:-2]
        logger.info("Read hardware response: '%s'", s)
        return s

    def _execute_checked_command(self, command, delay_before_status_read=None):
        """Execute the given response-less command, and check the hardware error 
        status afterwards (raising a ConexError if not nominal).
        """
        self._send_command(command)
        if delay_before_status_read is not None:
            time.sleep(delay_before_status_read)
        self.check_error()

    def _execute_config_mode_command(self, command):
        """Switch to configuration mode (PW1), execute the given response-less
        command, switch back to regular mode (PW0). Hardware errors are checked
        along the way (raising a ConexError if not nominal).

        Note that according to the documentation, the nominal endurance of the
        non-volatile is only 100 writes (i.e. switches out of configuration mode). This
        should thus be avoided if possible.
        """
        self._execute_checked_command("PW1", delay_before_status_read=1.0)
        try:
            self._execute_checked_command(command)
        finally:
            # PW0 writes to non-volatile storage and according to the documentation can
            # take up to 10 s, during which the controller remains unresponsive.
            # Alternatively, we could try sending TE until we get a response, but that
            # seems potentially more brittle.
            self._execute_checked_command("PW0", delay_before_status_read=10.0)

    def _execute_query(self, command_name, suffix=""):
        """Execute the given command and wait for the response, checking the response format."""
        self._send_command(command_name + suffix)
        response = self._read_line()
        if response[:3] != f"{CHANNEL_IDX}{command_name}":
            raise ValueError(f"Expected response to {command_name}, got '{response}'")
        return response[3:]

    def check_error(self):
        """Query the hardware error bits (TE) and raise if any are set."""
        code = self._execute_query("TE")
        if code == "@":
            # No errors.
            return
        # Get error message from device. Response always begins with code itself and a
        # space; strip that for cleaner error message.
        message = self._execute_query("TB", code)[2:]
        raise ConexError(code, message)

    def reset(self):
        """
        Clear any latched hardware errors (RS) and re-save
        the current software limits so they survive the reset.
        """

        # Perform the actual hardware reset
        self._execute_checked_command("RS")
        time.sleep(0.1)

    def home(self):
        """Go to home position—required after reset of controller before any
        other operation.
        
        Blocks until the operation is complete.
        """
        # 0: mech-zero + encoder index
        self._home_with_type("4")

    def _home_with_type(self, type):
        try:
            try:
                ht = self._execute_query("HT", "?")
                if ht != type:
                    logger.warning(
                        f"Changing home type (in persistent storage) from {ht} to {type}"
                    )
                    self._execute_config_mode_command(f"HT{type}")
                self._execute_checked_command("OR")
            except ConexError as e:
                if e.code != "K":
                    raise
                raise RuntimeError("Cannot home from current state; try reset() first")
            # Wait for it to finish
            while True:
                time.sleep(0.1)
                s = self.get_status()
                if s == StateType.Ready:
                    return
                if s != StateType.Homing:
                    raise RuntimeError(f"Unexpected state during home: {s}")
        finally:
            # Always at least attempt to set limits.
            try:
                self.set_lower_limit(self._cached_lower_limit)
            except:
                logger.exception("Failed to write lower limit")
            try:
                self.set_upper_limit(self._cached_upper_limit)
            except:
                logger.exception("Failed to write upper limit")

    def set_position(self, pos, blocking=True):
        """Go to an absolute position. If blocking, do no return until the stage
        has stopped moving"""
        self._execute_checked_command("PA{}".format(pos))
        if blocking:
            while True:
                time.sleep(10e-3)
                s = self.get_status()
                if s == StateType.Ready:
                    return
                elif s != StateType.Moving:
                    raise ValueError("State is not moving ({})".format(s))

    def stop(self):
        """Stop motion"""
        self._execute_checked_command("ST")

    def get_position(self):
        """Return the current position.

        This is the where the positioner actually is according to its encoder value. In
        MOVING state, this value always changes. In READY state, this value should be
        equal or very close to the set-point and target position.
        """
        pos_str = self._execute_query("TP")
        try:
            return float(pos_str)
        except ValueError:
            raise ValueError("Could not interpret responses '{}'".format(pos_str))

    def get_position_setpoint(self):
        """Return the position setpoint.

        This is where the positioner should be. In MOVING state, the set-point position
        changes according to the calculation of the motion profiler. In READY state, the
        set-point position is equal to the target position.
        """
        pos_str = self._execute_query("TH")
        try:
            return float(pos_str)
        except ValueError:
            raise ValueError("Could not interpret responses '{}'".format(pos_str))

    def set_upper_limit(self, limit, persist=False):
        """Set the upper limit.  
        If persist=True, also write it into non-volatile memory (write endurance limited to ~100 cycles)."""
        self._cached_upper_limit = limit

        # Use setpoint for check to avoid LSB fluctuations (e.g. around zero) causing
        # spurious failures.
        if limit < self.get_position_setpoint():
            raise ValueError("Upper limit must exceed current position")
        cmd = f"SR{limit}"
        if persist:
            # run in config mode to write to flash
            self._execute_config_mode_command(cmd)
        else:
            # just set in RAM
            self._execute_checked_command(cmd)

    def set_lower_limit(self, limit, persist=False):
        """Set the lower limit.  
        If persist=True, also write it into non-volatile memory (write endurance limited to ~100 cycles)."""
        self._cached_lower_limit = limit

        # Use setpoint for check to avoid LSB fluctuations (e.g. around zero) causing
        # spurious failures.
        curr_pos = self.get_position_setpoint()
        if limit > curr_pos:
            raise ValueError(
                f"Requested lower limit {limit} mm outside range for current position {curr_pos} mm"
            )
        cmd = f"SL{limit}"
        if persist:
            # run in config mode to write to flash
            self._execute_config_mode_command(cmd)
        else:
            # just set in RAM
            self._execute_checked_command(cmd)

    def get_upper_limit(self):
        pos_str = self._execute_query("SR", "?")
        try:
            pos = float(pos_str)
        except ValueError:
            raise ValueError("Could not interpret response '{}'".format(pos_str))
        return pos

    def get_lower_limit(self):
        pos_str = self._execute_query("SL", "?")
        try:
            pos = float(pos_str)
        except ValueError:
            raise ValueError("Could not interpret response '{}'".format(pos_str))
        return pos

    def get_status(self):
        """Return the status code of the controller"""
        code = self._execute_query("TS", "?")
        state_code = code[4:6].lower()
        if state_code in ["0a", "0b", "0c", "0d", "0e", "0f", "10"]:
            return StateType.NotReferenced
        if state_code == "1e":
            return StateType.Homing
        if state_code == "28":
            return StateType.Moving
        if state_code in ["32", "33", "34", "36"]:
            return StateType.Ready
        if state_code in ["3c", "3d", "3e", "3f"]:
            return StateType.Disable
        if state_code == "14":
            return StateType.Configuartion
        logger.warning(f"Uncategorised state: '{code}'")
        return StateType.Other

    def ping(self):
        return True
