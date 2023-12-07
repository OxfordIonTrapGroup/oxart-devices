""" Driver for SCPI Digital Multi-Meters """

from oxart.devices.streams import get_stream


class ScpiDmm:

    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def measure(self):
        """ Performs a measurement and returns the result.

        The device must already be configured. Note for slow measurements
        (low BW, high integration time, auto-zero enabled) over GPIB may hang
        due to the "read_eoi" command hitting a timeout. To avoid this, use
        :meth initiate_measurement: followed by :meth fetch_result:.
        """
        self.stream.write("READ?\n".encode())
        return float(self.stream.readline().decode())

    def initiate_measurement(self):
        """ Triggers a measurement, without transferring the results to the
        device's output buffer. The device must already be configured for
        the measurement.
        """
        self.stream.write("INIT\n".encode())

    def fetch_result(self):
        """ Fetch measurement results from the device's output buffer (see
        :meth initiate_measurement:) """
        self.stream.write("FETCH?\n".encode())
        return float(self.stream.readline().decode())

    def set_measurement_mode(self, mode):
        """ Set the measurement mode without initiating a measurement.

        :param mode: a measurement mode string. Typically one of: "volt:dc";
          "volt:dc:ratio"; "volt:ac"; "current:dc"; "current:ac"; "resistance";
          "fresistance" (4-wire resistance); "frequency"; "period";
          "continuity"; "diode"
          """
        self.stream.write('FUNC "{}"\n'.format(str(mode)).encode())

    def set_range(self, measurement_range):
        """ Sets the measurement range without initiating a measurement.

        :param measurement_range: the measurement range. Either a number or
          one of "min"; "max"
        """
        mode = self.get_measurement_mode()
        cmd = "{}:RANGE {}\n".format(mode, measurement_range)
        self.stream.write(cmd.encode())

    def set_auto_range(self, enabled):
        """ Enable or disable auto range for the current measurement mode """
        mode = self.get_measurement_mode().upper()
        self.stream.write("{}:RANGE:AUTO {}\n".format(
            mode, "ON" if enabled else "OFF").encode())

    def set_resolution(self, resolution):
        """ Sets the measurement resolution without initiating a measurement.

        :param resolution: the measurement resolution. Either a number or
          one of "min"; "max" (max is the worst resolution)
        """
        mode = self.get_measurement_mode()
        cmd = "{}:RANGE {}\n".format(mode, resolution)
        self.stream.write(cmd.encode())

    def set_integration_time(self, t_int):
        """ Sets the measurement integration time
        :param t_int: the measurement integration time in units of mains power
          cycles (NPLC). One of: 0.02, 0.2, 1, 10, 100, "min", "max"
        """
        if isinstance(t_int, int):
            t_int = float(t_int)
        if isinstance(t_int, str):
            t_int = t_int[0:3].lower()
        if t_int not in [0.02, 0.2, 1., 10., 100., "min", "max"]:
            raise ValueError("invalid t_int")

        mode = self.get_measurement_mode()
        self.stream.write("{}:NPLC {}\n".format(mode, t_int).encode())

    def set_bw(self, bandwidth):
        """ Sets the measurement bandwidth
        :param bandwidth: the measurement bandwidth (Hz), one of: 3; 20; 200;
          "min"; "max"
        """
        if isinstance(bandwidth, int):
            bandwidth = float(bandwidth)
        if isinstance(bandwidth, str):
            bandwidth = bandwidth[0:3].lower()
        if bandwidth not in [3., 20., 200., "min", "max"]:
            raise ValueError("invalid measurement bandwidth")
        self.stream.write("SENSE:DET:BAND {}\n".format(bandwidth).encode())

    def set_auto_zero(self, enabled):
        """ Enables or disables the auto-zeroing mode """
        mode = self.get_measurement_mode()
        if enabled:
            self.stream.write("{}:RANGE:AUTO ON\n".format(mode).encode())
        else:
            self.stream.write("{}:RANGE:AUTO OFF\n".format(mode).encode())

    def set_auto_impedance(self, enabled):
        """ Enables/disables auto input impedance mode.

        Only affects DC voltage measurements. With auto impedance off, the
        input impedance is 10M for all ranges. With it on, the impedance is
        >10G for the 0.1V, 1V and 10V ranges.
        """
        if enabled:
            self.stream.write("INPUT:IMPEDANCE:AUTO ON\n".encode())
        else:
            self.stream.write("INPUT:IMPEDANCE:AUTO OFF\n".encode())

    def get_measurement_mode(self):
        """ Returns a measurement type string, such as "volt". """
        self.stream.write("FUNC?\n".encode())
        return self.stream.readline().decode().strip('"').lower()

    def get_range(self):
        """ Returns the current measurement range as a float
        NB this disables auto-range
        """
        mode = self.get_measurement_mode()
        self.stream.write("{}:RANGE?\n".format(mode).encode())
        return float(self.stream.readline().decode())

    def get_auto_range(self):
        """ Returns True if auto range is enabled otherwise False """
        mode = self.get_measurement_mode()
        self.stream.write("{}:RANGE:AUTO?\n".format(mode).encode())
        return bool(int(self.stream.readline().decode()))

    def get_resolution(self):
        """ Returns the current measurement range as a float """
        mode = self.get_measurement_mode()
        self.stream.write("{}:RES?\n".format(mode).encode())
        return float(self.stream.readline().decode())

    def get_integration_time(self):
        """
        Returns the current integration time in units of mains power cycles
        (NPLC).
        """
        mode = self.get_measurement_mode()
        self.stream.write("{}:NPLC?\n".format(mode).encode())
        return float(self.stream.readline().decode())

    def get_bw(self):
        """ Returns the current measurement bandwidth in Hz """
        self.stream.write("SENSE:DETECTOR:BANDWIDTH?\n".encode())
        return float(self.stream.readline().decode())

    def get_auto_zero(self):
        """ Returns True if auto-zero mode is enabled, otherwise False """
        self.stream.write("SENSE:ZERO:AUTO?\n".encode())
        return bool(int(self.stream.readline().decode()))

    def get_input(self):
        """
        Returns True if the front input terminals are used or False if the rear
        terminals are used.

        NB this cannot be set from software!
        """
        self.stream.write("ROUTE:TERMINALS?\n".encode())
        ret = self.stream.readline().decode().strip('"').lower()
        if ret == "fron":
            return True
        elif ret == "rear":
            return False
        else:
            raise ValueError("Unrecognised response from DMM: {}".format(ret))

    def get_auto_impedance(self):
        """ Returns True if auto impedance mode is active.

        Only affects DC voltage measurements. With auto impedance off, the
        input impedance is 10M for all ranges. With it on, the impedance is
        >10G for the 0.1V, 1V and 10V ranges.
        """
        self.stream.write("INPUT:IMPEDANCE:AUTO?\n".encode())
        return bool(int(self.stream.readline().decode()))

    def ping(self):
        return bool(self.identify())

    def close(self):
        self.stream.close()
