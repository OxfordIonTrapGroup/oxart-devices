import socket
import numpy as np


def _validate_channel(channel):
    if not isinstance(channel, int) and not isinstance(channel, np.int32):
        raise ValueError("channel must be an int")
    if (channel < 0) or (channel > 7):
        raise ValueError("invalid channel number {}".format(channel))


class Booster:
    """ Booster 8-channel RF PA """
    def __init__(self, device):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((device, 5000))
        self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        self.ip_addr = device
        assert self.ping()

    def identify(self):
        """ Returns a device identification string """
        self.sock.send("*IDN?\r\n".encode())
        with self.sock.makefile() as stream:
            return stream.readline().strip()

    def get_version(self):
        """
        Returns tuple of the revision number as a float, and the build date as
        a string
        """
        idn = self.identify().lower().split(',')
        hw_rev = float(idn[2])
        fw_build = idn[3].strip()
        return hw_rev, fw_build

    def ping(self):
        """ Returns True if we are connected to a Booster """
        idn = self.identify().lower().split(',')
        return idn[0:2] == ["wut", "rfpa booster"]

    def _cmd(self, cmd, channel, arg=None):
        _validate_channel(channel)
        if arg is not None:
            full_cmd = "{} {},{}".format(cmd, channel, arg)
        else:
            full_cmd = "{} {}".format(cmd, channel)
        self.sock.send((full_cmd+'\n').encode())

        if '?' not in cmd:
            return

        with self.sock.makefile() as stream:
            response = stream.readline().lower().strip()
            # print("RESPONSE: "+response)

            if ('?' not in cmd and response != "okay") or \
               ('?' in cmd and 'error' in response):
                raise Exception("Unrecognised response to '{}': '{}'".format(
                    full_cmd, response))
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

    def set_enabled(self, channel, enabled=True):
        """ Enables/disables a channel. """
        if enabled:
            cmd = "CHAN:ENAB"
        else:
            cmd = "CHAN:DISAB"
        self._cmd(cmd, channel)

    def get_enabled(self, channel):
        """ Query if a channel is enabled """
        return bool(self._cmd("CHAN:ENAB?", channel))

    def set_output_interlock(self, channel, threshold):
        """ Sets the output forward power interlock threshold for a channel in
        dBm.

        This setting is stored in non-volatile memory and retained across power
        cycles.

        :param threshold: must lie between 0dBm and 38dBm
        """
        if (threshold < 0) or (threshold > 38):
            raise ValueError("Output forward power interlock threshold must "
                             "lie between 0dBm and +38dBm")
        self._cmd("INT:POW", channel, "{:.2f}".format(threshold))

    def get_output_interlock(self, channel):
        """
        Returns the output forward power interlock threshold for a channel in
        dBm.
        """
        return float(self._cmd("INT:POW?", channel))

    def get_interlock_tripped(self, channel):
        """
        Returns True if any of the interlocks on a channel have tripped, or
        False if the channel is operating normally
        """
        return self._query_bool("INT:STAT?", channel)

    def get_overload_status(self, channel):
        """
        Returns True if the power interlock for a channel is okay, False if
        it has tripped.
        """
        return self._query_bool("INT:OVER?", channel)

    def get_temperature(self, channel):
        """ Returns the temperature of a channel in C """
        return float(self._cmd("MEAS:TEMP?", channel))

    def clear_interlock(self, channel):
        """ Resets all interlocks for a channel. """
        self._cmd("INT:CLEAR", channel)

    def get_output_power(self, channel):
        """ Returns the output power for a channel in dBm """
        return float(self._cmd("MEAS:OUT?", channel))

    def get_reverse_power(self, channel):
        """ Returns the output reflected power for a channel in dBm """
        return float(self._cmd("MEAS:REV?", channel))

    def close(self):
        self.sock.close()
