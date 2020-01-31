from oxart.devices.streams import get_stream


class Agilent6671A:
    """Driver for Agilent 6671A power supplies"""

    def __init__(self, device, timeout=10):
        # If the Agilent 6671A is connected via a GPIB adapter, the adapter
        # will be pinged as part of the call to get_stream. If no
        # AssertionError is raised, the adapter is responding
        self.stream = get_stream(device, timeout=timeout)

        # Adapter can be reached, so now ping device itself
        assert self.ping(), "Agilent 6671A not responding to ping"

    def get_voltage(self):
        """Return the measured output voltage."""
        return self._get_float("MEAS:VOLT?")

    def get_current(self):
        """Return the measured output current."""
        return self._get_float("MEAS:CURR?")

    def get_output(self):
        """Return True if the output is on, else False."""
        return self._get_bool("OUTP?")

    def get_voltage_limit(self):
        """Return the voltage limit for channel in volts."""
        return self._get_float(":VOLT?")

    def get_current_limit(self):
        """Return the current limit for channel in amps."""
        return self._get_float(":CURR?")

    def set_voltage_limit(self, voltage_limit):
        """Set the voltage limit for channel in volts."""
        self.stream.write(":VOLT {:f}".format(voltage_limit))

    def set_current_limit(self, current_limit):
        """Set the current limit for channel in amps"""
        self.stream.write(":CURR {:f}".format(current_limit))

    def set_output_enable(self, enable):
        """Enable/disable a channel."""
        self.stream.write("OUTP {}".format(int(bool(enable))).encode())

    def set_overvoltage_limit(self, overvoltage_limit):
        """Set the overvoltage protection (OVP) level of the power supply.

        If the output voltage exceeds the OVP level, then the power supply
        output is disabled and the "questionable condition" status register OV
        bit is set (see "Chapter 4 - Status Reporting"). An overvoltage
        condition can be cleared with the OUTP:PROT:CLE command after the
        condition that caused the OVP to trip has been removed.
        """
        self.stream.write("VOLT:PROT {:f}".format(overvoltage_limit))

    def clear_all_interlocks(self):
        """Reset the OV (over voltage), OC (over current), OT (over
        temperature) and RI (remote inhibit) protection interlocks.

        After this command, the output is restored to the state it was in
        before the protection activated.
        """
        self.stream.write("OUTP:PROT:CLE\n".encode())

    def get_error_status(self):
        """Return an integer with the PSU "questionable" status register.

        0 indicates normal operation

        Bits are:
        - 0 : over voltage error
        - 1 : over current
        - 4 : over temperature
        - 9 : remote inhibit
        - 10 : power supply output out of regulation
        """
        return self._get_int("STAT:QUES?")

    def reset(self):
        """Reset device to factory settings."""
        self.stream.write("*RST")

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def ping(self):
        ident = self.identify().lower().split(",")
        ident = [sub_str.strip() for sub_str in ident]
        return ident[0:2] == ["hewlett-packard", "6671a"]

    def close(self):
        self.stream.close()

    def _get_float(self, cmd):
        self.stream.write((cmd+"\n").encode())
        return float(self.stream.readline().decode())

    def _get_bool(self, cmd):
        self.stream.write((cmd+"\n").encode())
        return bool(self.stream.readline().decode())

    def _get_int(self, cmd):
        self.stream.write((cmd+"\n").encode())
        return int(self.stream.readline().decode())
