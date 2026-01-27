import serial


class V3500A:
    """USB driver for Keysight V3500A RF Power Meters.

    Windows only, assumes USB driver is installed; if not, download from
    https://www.keysight.com/main/software.jspx?ckey=sw287
    """

    def __init__(self, device):
        self.bus = serial.serial_for_url(device, baudrate=9600)
        assert self.ping()

    def ping(self):
        return bool(self.get_firmware_rev())

    def close(self):
        self.bus.close()

    def _set(self, cmd):
        """Send a command to the power meter and check that the response is "OK"."""
        self.bus.write(cmd.encode())
        response = self.bus.readline().decode()
        if response != "OK\n":
            raise ValueError("Unrecognised response: " + response)

    def reset(self):
        """Reset device to power-on default state."""
        self._set("*RST\n")

    def get_serial(self):
        """Returns the device's serial number as an integer."""
        self.bus.write("SN?\n".encode())
        return int(self.bus.readline().decode())

    def get_firmware_rev(self):
        """Returns the device's firmware revision string."""
        self.bus.write("FWREV?\n".encode())
        return self.bus.readline().decode().rstrip("\n")

    def read(self, trigger=True):
        """Take a power reading.

        If trigger is True (default) then we begin a new measurement cycle otherwise, we
        return the last result. NB untriggered reads can give unpredictable results if
        the power changes during the measurement cycle.
        """
        if trigger:
            self.bus.write("*TRG\n".encode())
        else:
            self.bus.write("PWR?\n".encode())
        return float(self.bus.readline().decode())

    def zero(self):
        """Zero the measured power to remove device's offset."""
        self._set("ZERO\n")

    def set_freq(self, freq):
        """The the operating frequency in MHz."""
        self._set("FREQ {}\n".format(freq))

    def set_averaging(self, avg=0):
        """Sets the number of measurements taken during each measurement cycle.

        The number of measurements taken is given by (2**avg), where avg is an integer
        between 0 (no averaging) and 5 (32 measurements).
        """
        self._set("SETAVG {:d}\n".format(avg))

    def get_averaging(self):
        """Returns the averaging factor.

        The number of measurements averaged over in each measurement cycle is given by
        2**avgeraging_factor.
        """
        self.bus.write("AVG?\n".encode())
        return int(self.bus.readline().decode())

    def set_fast_mode(self, enabled=True):
        """Enables the device's "fast mode", giving faster results at the expense of
        reduced accuracy."""
        if enabled:
            self._set("HSMODE\n")
        else:
            self._set("NMODE\n")

    def set_db_units(self, enabled=True):
        """If enabled is True, measurements are returned in dBm, otherwise they are
        returned in Watts."""
        if enabled:
            self._set("UDBM\n")
        else:
            self._set("UMW\n")

    def set_backlight(self, enabled=True):
        """Enable or disable the backlight."""
        if enabled:
            self._set("BLON\n")
        else:
            self._set("BLOFF\n")
