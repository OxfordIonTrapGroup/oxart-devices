""" Driver for 6671A power supplies """

from oxart.devices.streams import get_stream


class Agilent6671A:

    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def _get_float(self, cmd):
        self.stream.write((cmd+"\n").encode())
        return float(self.stream.readline().decode())

    def _get_bool(self, cmd):
        self.stream.write((cmd+"\n").encode())
        return bool(self.stream.readline().decode())

    def _get_int(self, cmd):
        self.stream.write((cmd+"\n").encode())
        return int(self.stream.readline().decode())

    def get_current(self):
        """ Returns the measured output current. """
        return self._get_float("MEAS:CURR?")

    def get_voltage(self):
        """ Returns the measured output voltage. """
        return self._get_float("MEAS:VOLT?")

    def get_output(self):
        """ Returns True if the output is on, else False """
        return self._get_bool("OUTP?")

    def clear_output_protection(self):
        """ Resets the OV (over voltage), OC (over current), OT (over
        temperature) and RI (remote inhibit) protection interlocks.

        After this command, the output is restored to the state it was in
        before the protection activated.
        """
        self.stream.write("OUTP:PROT:CLE\n".encode())

    def get_error_status(self):
        """ Returns an integer with the PSU "questionable" status register.

        0 indicates normal operation

        Bits are:
        - 0 : over voltage error
        - 1 : over current
        - 4 : over temperature
        - 9 : remote inhibit
        - 10 : power supply output out of regulation
        """
        return self._get_int("STAT:QUES?")

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def ping(self):
        ident = self.identify().lower().split(",")
        ident = [sub_str.strip() for sub_str in ident]
        return ident[0:2] == ["hewlett-packard", "6671a"]

    def close(self):
        self.stream.close()
