import collections
import dateutil.parser
import math
import serial

Version = collections.namedtuple(
    "Version", ["fw_rev", "fw_hash", "fw_build_date", "device_id", "hw_rev"])

Status = collections.namedtuple("Status", [
    "detected", "enabled", "interlock", "output_power_mu", "reflected_power_mu", "I29V",
    "I6V", "V5VMP", "temp", "output_power", "reflected_power", "input_power",
    "fan_speed", "error_occurred", "hw_id", "i2c_error_count"
])


class Booster:
    """ Booster 8-channel RF PA """

    def __init__(self, device):
        self.dev = serial.serial_for_url("socket://{}:5000".format(device))
        self.dev.timeout = 1
        self.dev.flushInput()
        assert self.ping()

    def _cmd(self, cmd, channel, arg=None):

        if channel is not None and channel not in range(8):
            raise ValueError("invalid channel number {}".format(channel))

        if channel is None and arg is None:
            cmd = (cmd + '\n')
        elif arg is None:
            cmd = "{} {}\n".format(cmd, channel)
        else:
            cmd = "{} {}, {}\n".format(cmd, channel, arg)
        self.dev.write(cmd.encode())

        response = self.dev.readline().decode()
        if response == '':
            self.dev.write(b'\n')
            response = self.dev.readline().decode()
            self.dev.readline()  # blank response from extra write
            if response == '':
                raise serial.SerialTimeoutException(
                    "Timeout while waiting for response to '{}'".format(cmd.strip()))
        response = response.lower().strip()

        if '?' in cmd and "error" not in response:
            return response
        elif response == "ok":
            return

        raise Exception("Unrecognised response to '{}': '{}'".format(cmd, response))

    def _query_bool(self, cmd, channel, arg=None):
        resp = self._cmd(cmd, channel, arg)
        if resp == "0":
            return False
        elif resp == "1":
            return True
        else:
            raise Exception("Unrecognised response to {}: '{}'".format(cmd, resp))

    def _query_float(self, cmd, channel, arg=None):
        resp = self._cmd(cmd, channel, arg)
        try:
            return float(resp)
        except ValueError:
            raise Exception("Unrecognised response to {}: '{}'".format(cmd, resp))

    def get_version(self):
        """ Returns the device version information as a named tuple """
        self.dev.write(b"*IDN?\n")
        idn = self.dev.readline().decode().strip().lower().split(',')

        idn[0] = idn[0].split(" ")

        if (idn[0][0] != "rfpa" or not idn[1].startswith(" built ")
                or not idn[2].startswith(" id ") or not idn[3].startswith(" hw rev ")):
            raise Exception("Unrecognised device identity string: {}".format(idn))

        return Version(fw_rev=idn[0][1],
                       fw_hash=idn[0][2],
                       fw_build_date=dateutil.parser.parse(idn[1][7:]),
                       device_id=idn[2][4:],
                       hw_rev=idn[3][1:])

    def get_version_dict(self):
        """Return device version information, as a dictionary.

        This is the same as :meth:`get_version`, but as a dictionary rather than a named
        tuple to be compatible with PYON for use as an ARTIQ controller.
        """
        result = self.get_version()._asdict()
        result["fw_build_date"] = str(result["fw_build_date"])
        return result

    def ping(self):
        """ Returns True if we are connected to a Booster """
        try:
            self.get_version()
        except Exception:
            return False
        return True

    def set_enabled(self, channel, enabled=True):
        """ Enables/disables a channel """
        cmd = "CHAN:ENAB" if enabled else "CHAN:DISAB"
        self._cmd(cmd, channel)

    def get_enabled(self, channel):
        """ Returns True is the channel is enabled """
        return self._query_bool("CHAN:ENAB?", channel)

    def get_detected(self, channel):
        """ Returns True is the channel is detected, otherwise False.

        Non-detected channels indicate a serious hardware error!
        """
        return self._query_bool("CHAN:DET?", channel)

    def get_status(self, channel):
        """ Returns a named tuple containing information about the status
        of a given channel.

        NB powers below the detector sensitivity are recorded as nan

        Fields are:
        detected: True if the channel is detected
        enabled: True if the channel was enabled
        interlock: True if the interlock has tripped for this channel
        output_power_mu: output (forward) power detector raw ADC value
        reflected_power_mu: output reverse power detector raw ADC value
        output_power: output (forward) power (dBm)
        reflected_power: output reverse power (dBm)
        input_power: input power (dBm)
        I29V: current consumption on the main 29V rail (A)
        I6V: current consumption on the 6V (preamp) rail (A)
        V5VMP: voltage on the 5VMP rail
        temp: channel temperature (C)
        fan_speed: chassis fan speed (%)
        error_occurred: True if an error (e.g over temperature) has occurred,
          otherwise False. Error conditions can only be cleared by
          power-cycling Booster.
        hw_id: unique ID number for the channel
        i2c_error_count: number of I2C bus errors that have been detected for
          this channel.
        """
        resp = self._cmd("CHAN:DIAG?", channel).split(',')

        if len(resp) != 22:
            raise Exception("Unrecognised response to 'CHAN:DIAG?': {}".format(resp))

        def _bool(value_str):
            if value_str == "1":
                return True
            elif value_str == "0":
                return False
            raise Exception("Unrecognised response to 'CHAN:DIAG?': {}".format(resp))

        return Status(detected=_bool(resp[0]),
                      enabled=_bool(resp[1]),
                      interlock=_bool(resp[2]),
                      output_power_mu=int(resp[4]),
                      reflected_power_mu=int(resp[5]),
                      I29V=float(resp[6]),
                      I6V=float(resp[7]),
                      V5VMP=float(resp[8]),
                      temp=float(resp[9]),
                      output_power=float(resp[10]),
                      reflected_power=float(resp[11]),
                      input_power=float(resp[12]),
                      fan_speed=float(resp[13]),
                      error_occurred=_bool(resp[14]),
                      hw_id="{:x}:{:x}:{:x}:{:x}:{:x}:{:x}".format(
                          *[int(part) for part in resp[15:21]]),
                      i2c_error_count=int(resp[21]))

    def get_status_dict(self, channel):
        """Return status of a given channel, as a dictionary.

        This is the same as :meth:`get_status`, but as a dictionary rather than a named
        tuple to be compatible with PYON for use as an ARTIQ controller. See the former
        for a description of the individual fields.
        """
        return self.get_status(channel)._asdict()

    def get_current(self, channel):
        """ Returns the FET bias current (A) for a given channel. """
        return self._query_float("MEAS:CURR?", channel)

    def get_temperature(self, channel):
        """ Returns the temperature (C) for a given channel. """
        return self._query_float("MEAS:TEMP?", channel)

    def get_output_power(self, channel):
        """ Returns the output (forwards) power for a channel in dBm """
        return self._query_float("MEAS:OUT?", channel)

    def get_input_power(self, channel):
        """ Returns the input power for a channel in dBm """
        val = self._query_float("MEAS:IN?", channel)
        if math.isnan(val):
            raise Exception(
                "Input power detector not calibrated for channel {}".format(channel))
        return val

    def get_reflected_power(self, channel):
        """ Returns the reflected power for a channel in dBm """
        return self._query_float("MEAS:REV?", channel)

    def get_fan_speed(self):
        """ Returns the fan speed as a number between 0 and 100"""
        return self._query_float("MEAS:FAN?", None)

    def set_interlock(self, channel, threshold):
        """ Sets the output forward power interlock threshold (dBm) for a
        given channel channel.

        This setting is stored in non-volatile memory and retained across power
        cycles.

        :param threshold: must lie between 0dBm and 38dBm
        """
        if (threshold < 0) or (threshold > 38):
            raise ValueError("Output forward power interlock threshold must "
                             "lie between 0dBm and +38dBm")
        self._cmd("INT:POW", channel, "{:.2f}".format(threshold))

    def get_interlock(self, channel):
        """ Returns the output forward power interlock threshold (dBm) for a
        channel.
        """
        return self._query_float("INT:POW?", channel)

    def clear_interlock(self, channel):
        """ Resets the forward and reverse power interlocks for a given
        channel. """
        self._cmd("INT:CLEAR", channel)

    def get_interlock_tripped(self, channel):
        """ Returns True if the output forwards or reverse power interlock
        has tripped for a given channel. """
        return self._query_bool("INT:STAT?", channel)

    def get_forward_power_interlock_tripped(self, channel):
        """ Returns True if the output forwards power interlock has tripped for
        a given channel. """
        return self._query_bool("INT:FOR?", channel)

    def get_reverse_power_interlock_tripped(self, channel):
        """ Returns True if the output forwards power interlock has tripped for
        a given channel. """
        return self._query_bool("INT:REV?", channel)

    def get_error_occurred(self, channel):
        """ Returns True if a device error (over temperature etc) has occurred
        on a given channel """
        return self._query_bool("INT:ERR?", channel)

    def close(self):
        self.dev.close()
