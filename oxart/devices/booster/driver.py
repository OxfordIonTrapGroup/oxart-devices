import serial


class Booster:
    """ Booster 8-channel RF PA """
    def __init__(self, device):
        self.dev = serial.serial_for_url("socket://{}:5000".format(device))
        self.dev.flushInput()
        assert self.ping()

    def identify(self):
        """ Returns a device identification string """
        self.dev.write(b"*IDN?\n")
        idn = self.dev.readline().decode().strip()
        return idn

    def get_version(self):
        """ Returns tuple of the revision number as a float, and the build date as
        a string
        """
        # to do
        # idn = self.identify().lower().split(',')
        # hw_rev = float(idn[2])
        # fw_build = idn[3].strip()
        # return hw_rev, fw_build
        return None

    def ping(self):
        """ Returns True if we are connected to a Booster """
        idn = self.identify().lower().split(' ')
        return idn[0] == "rfpa"

    def _cmd(self, cmd, channel, arg=None):
        if self.dev.in_waiting:
            # self.dev.flushInput()  # to do: remove when fw doesn't suck
            print(self.dev.readline())
            raise ValueError("CRAP IN BUFFER, OH DEAR!!")

        # if channel not in range(8):
        #     raise ValueError("invalid channel number {}".format(channel))

        if arg is None:
            cmd = "{} {}\n".format(cmd, channel)
        else:
            cmd = "{} {}, {}\n".format(cmd, channel, arg)

        print("CMD: " + cmd + "...")
        self.dev.write(cmd.encode())

        response = self.dev.readline().decode().lower().strip()
        print("resp: " + response)

        # if ('?' not in cmd and response != "okay") or \
        # ('?' in cmd and 'error' in response):
        # raise Exception("Unrecognised response to '{}': '{}'".format(
        # full_cmd, response))
        return response

    def _query_bool(self, cmd, channel, arg=None):
        resp = self._cmd(cmd, channel, arg)
        if resp == "0":
            return False
        elif resp == "1":
            return True
        else:
            raise Exception(
                "Unrecognised response to {}: '{}'".format(cmd, resp))

    def _query_float(self, cmd, channel, arg=None):
        resp = self._cmd(cmd, channel, arg)
        try:
            return float(resp)
        except ValueError:
            raise Exception(
                "Unrecognised response to {}: '{}'".format(cmd, resp))

    def set_enabled(self, channel, enabled=True):
        """ Enables/disables a channel. """
        cmd = "CHAN:ENAB" if enabled else "CHAN:DISAB"
        self._cmd(cmd, channel)

    def get_enabled(self, channel):
        """ Query whether a channel is enabled """
        return self._query_bool("CHAN:ENAB?", channel)

    def get_detected(self, channel):
        """ Returns True is the channel is detected, otherwise False.

        Non-detected channels indicate a serious hardware error!
        """
        return self._query_bool("CHAN:DET?", channel)

    def get_current(self, channel):
        """ Returns the FET bias current (A) for a given channel. """
        return self._query_float("MEAS:CURR?", channel)

    def get_temperature(self, channel):
        """ Returns the temperature (C) for a given channel. """
        return self._query_float("MEAS:TEMP?", channel)

    def get_power(self, channel):
        """ Returns the output (forwards) power for a channel in dBm """
        return self._query_float("MEAS:OUT?", channel)

    def get_reflected(self, channel):
        """ Returns the reflected power for a channel in dBm """
        return self._query_float("MEAS:REV?", channel)

    def get_fan(self):
        """ Returns the fan speed as a number between 0 and 1"""
        return self._query_float("MEAS:FAN?", "")

    def set_interlock(self, channel, threshold):
        """
        Sets the output forward power interlock threshold (dBm) for a channel.

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
        """ Resets the interlock for a given channel. """
        self._cmd("INT:CLEAR", channel)

    def get_interlock_tripped(self, channel):
        """
        Returns True if any of the interlocks on a channel have tripped, or
        False if the channel is operating normally
        """
        return self._query_bool("INT:STAT?", channel)

    # def get_overload_status(self, channel):
    #     """
    #     Returns True if the power interlock for a channel is okay, False if
    #     it has tripped.
    #     """
    #     return self._query_bool("INT:OVER?", channel)

    # def get_diagnostics(self, channel):
    #     """ Channe """
    #     return self._cmd("INT:DIAG?", channel)

    def close(self):
        self.dev.close()
