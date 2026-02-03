import serial


class Arroyo:
    """Driver for Arroyo laser/TEC controllers.

    This driver is not exhaustive; see documentation at
    https://www.arroyoinstruments.com/wp-content/uploads/2021/01/ArroyoComputerInterfacingManual.pdf
    """

    def __init__(self, address, timeout=0.1, **kwargs):
        self.device = serial.serial_for_url(
            address, baudrate=38400, timeout=timeout, write_timeout=timeout, **kwargs
        )
        self.id = self.identify()

    def close(self):
        self.device.close()

    def _write(self, cmd):
        self.device.write(f"{cmd}\r\n".encode())

    def _readline(self):
        return self.device.readline().decode().strip()

    def _query(self, cmd):
        self._write(cmd)
        return self._readline()

    def identify(self):
        """Return device ID string."""
        return self._query("*IDN?")

    def ping(self):
        return bool(self.identify().lower().split(","))

    def get_errors(self):
        """Get human readable list of errors.

        Returns an empty list if there are no errors.
        """
        errs = iter(s.strip('"') for s in self._query("errstr?").split(","))
        return list(zip(errs, errs))

    def set_laser_output(self, enable):
        """Set laser output on/off (True/False)"""
        self._write(f"laser:output {int(enable)}")

    def get_laser_output(self):
        """Get laser output status."""
        return bool(int(self._query("laser:output?")))

    def get_laser_mode(self):
        """Get laser operational mode.

        e.g. current control, photodiode current control etc
        """
        return self._query("laser:mode?")

    def set_laser_current(self, current):
        """Set laser current setpoint in mA."""
        self._write(f"laser:ldi {current:.3f}")

    def get_laser_current(self):
        """Get actual laser current in mA."""
        return float(self._query("laser:ldi?"))

    def get_laser_current_setpoint(self):
        """Get laser current setpoint in mA."""
        return float(self._query("laser:set:ldi?"))

    def set_laser_pd_current(self, current):
        """Set laser photodiode current setpoint in µA."""
        self._write(f"laser:mdi {current:.3f}")

    def get_laser_pd_current(self):
        """Get actual laser photodiode current in µA."""
        return float(self._query("laser:mdi?"))

    def get_laser_pd_current_setpoint(self):
        """Get laser photodiode current setpoint in µA."""
        return float(self._query("laser:set:mdi?"))

    def set_laser_pd_power(self, power):
        """Set laser photodiode power setpoint in mW.

        Only valid if photodiode responsivity has been configured.
        """
        self._write(f"laser:mdp {power:.3f}")

    def get_laser_pd_power(self):
        """Get actual laser photodiode power in mW.

        Only valid if photodiode responsivity has been configured.
        """
        return float(self._query("laser:mdp?"))

    def get_laser_pd_power_setpoint(self):
        """Get laser photodiode power setpoint in mW.

        Only valid if photodiode responsivity has been configured.
        """
        return float(self._query("laser:set:mdp?"))

    def set_laser_pd_responsivity(self, responsivity):
        """Set laser photodiode responsivity in µA/mW."""
        self._write(f"laser:calpd {responsivity:.4f}")

    def get_laser_pd_responsivity(self):
        """Get laser photodiode responsity in µA/mW."""
        return float(self._query("laser:calpd?"))

    def set_tec_output(self, enable):
        """Set TEC output on/off (True/False)"""
        self._write(f"tec:output {int(enable)}")

    def get_tec_output(self):
        """Get tec output status."""
        return bool(int(self._query("tec:output?")))

    def set_tec_temperature(self, temperature):
        """Set TEC setpoint in Celsius."""
        self._write(f"tec:t {temperature:.3f}")

    def get_tec_temperature(self):
        """Get actual TEC temperature in Celsius."""
        return float(self._query("tec:t?"))

    def get_tec_temperature_setpoint(self):
        """Get TEC temperature setpoint in Celsius."""
        return float(self._query("tec:set:t?"))
