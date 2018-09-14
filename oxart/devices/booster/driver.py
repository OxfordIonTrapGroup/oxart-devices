import socket
import numpy as np


def _validate_channel(channel):
    if not isinstance(channel, int) and not isinstance(channel, np.int32):
        raise ValueError("channel must be an int")
    if (channel < 0) or (channel > 7):
        raise ValueError("invalid channel number {}".format(channel))


class Booster:
    """ Booster 8-channel RF PA """
    def __init__(self, ip_addr):

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip_addr, 5000))
        self.ip_addr = ip_addr
        assert self.ping()

    def identify(self):
        """ Returns a device identification string """
        print("ping!")
        self.sock.send("*IDN?\r\n".encode())
        with self.sock.makefile() as stream:
            line = stream.readline().strip()
            print(line)
            return line

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

    def _cmd(self, channel, cmd, arg=""):
        _validate_channel(channel)
        if arg != "":
            full_cmd = "{} {},{}".format(cmd, channel, arg)
        else:
            full_cmd = "{} {}".format(cmd, channel)
        self.sock.send((full_cmd+'\r\n').encode())

        # deleteme!
        if '?' not in cmd:
            import time
            time.sleep(0.3)
            return

        with self.sock.makefile() as stream:
            response = stream.readline().lower().strip()

            if ('?' not in cmd and response != "okay") or \
               ('?' in cmd and 'error' in response):
                raise Exception("Unrecognised response to '{}': '{}'".format(
                    full_cmd, response))
            return response

    def _query_bool(self, channel, cmd, arg=""):
        resp = self._cmd(channel, cmd, arg)
        if resp == "0":
            return False
        elif resp == "1":
            return True
        else:
            raise Exception(
                "Unrecognised response to {}: '{}'".format(cmd, resp))

    def set_enabled(self, channel, enabled=True):
        """ Enables/disables a channel. """
        self._cmd(channel, "CHAN:ENABLE", str(int(enabled)))

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
        self._cmd(channel, "INT:HPOW", "{:.2f}".format(threshold))

    def get_output_interlock(self, channel):
        """
        Returns the output forward power interlock threshold for a channel in
        dBm.
        """
        return float(self._cmd(channel, "INT:HPOW?"))

    def get_interlock_status(self, channel):
        """
        Returns True if all interlocks for a channel are okay, False if an
        interlock has tripped.
        """
        return not self._query_bool(channel, "INT:STAT?")

    def get_overload_status(self, channel):
        """
        Returns True if the power interlock for a channel is okay, False if
        it has tripped.
        """
        return self._query_bool(channel, "INT:OVER?")

    def get_temperature(self, channel):
        """ Returns the temperature of a channel in C """
        return float(self._cmd(channel, "MEAS:TEMP?"))

    def clear_interlock(self, channel):
        """ Resets all interlocks for a channel. """
        self._cmd(channel, "INT:CLEAR")

    def get_output_power(self, channel):
        """ Returns the output power for a channel in dBm """
        return float(self._cmd(channel, "MEAS:OUT?"))

    def get_reverse_power(self, channel):
        """ Returns the output reflected power for a channel in dBm """
        return float(self._cmd(channel, "MEAS:REV?"))

    def close(self):
        self.sock.close()


def main():
    pa = Booster("10.255.6.216")
    [pa.set_output_interlock(ch, 30) for ch in range(8)]
    for channel in range(7):
        print("{}: {}".format(channel, pa.get_interlock_status(channel)))
    # to do: trip temperature interlock and check difference between interlock
    # status and overload status


if __name__ == "__main__":
    main()
