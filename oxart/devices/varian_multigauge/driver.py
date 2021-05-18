import serial


class VarianError(Exception):
    pass


class VarianIonGauge:
    """Varian ion-gauge driver"""
    def __init__(self, port, baudrate=19200, timeout=1):

        self.s = serial.Serial(port, baudrate, timeout=timeout)
        self.s.reset_input_buffer()

        self.set_pressure_units()

    def _send_command(self, command):

        line = "#00{}\r\n".format(command)
        self.s.write(line.encode())

        response = self._read_response()
        if response[0] != ord(b">"):
            raise VarianError("Received error response from gauge: " +
                              response.decode())

        return response[1:]

    def _read_response(self):
        return self.s.readline()

    def ping(self):
        try:
            self.read_emission_status(1)
        except Exception:
            return False
        return True

    def set_emission_status(self, channel, emission_on):
        command = "3{:01d}I{:01d}".format(int(emission_on), channel)
        self._send_command(command)

    def read_emission_status(self, channel):
        command = "32I{:01d}".format(channel)
        response = self._send_command(command)

        try:
            emission = bool(int(response))
        except ValueError:
            raise VarianError("Received bad response: {}".format(response))

        return emission

    def _set_emission_on_fil2(self, channel):
        command = "33I{:01d}".format(channel)
        self._send_command(command)

    def set_emission_status_fil2(self, channel, emission_on):
        """NB: setting filament 2 emission off will also set filament 1 off"""
        if emission_on:
            self._set_emission_on_fil2(channel)
        else:
            self.set_emission_status(channel, False)

    def read_filament_lit(self, channel):
        command = "34I{:01d}".format(channel)
        response = self._send_command(command)

        try:
            filament = int(response)
        except ValueError:
            raise VarianError("Received bad response: {}".format(response))

        return filament

    def set_degas_status(self, channel, degas_on):
        command = "4{:01d}I{:01d}".format(int(degas_on), channel)
        self._send_command(command)

    def read_degas_status(self, channel):
        command = "42I{:01d}".format(channel)
        response = self._send_command(command)

        try:
            degas = bool(int(response))
        except ValueError:
            raise VarianError("Received bad response: {}".format(response))

        return degas

    def set_pressure_units(self):
        """Set the pressure to sane units (mBar)"""
        self._send_command("11")

    def read_pressure(self, channel):
        command = "02I{:01d}".format(channel)
        response = self._send_command(command)

        try:
            pressure = float(response)
        except ValueError:
            # if the reponse cannot be cast to a float
            if response[0] == "E":
                raise VarianError("Received gauge error: {}".format(response))
            else:
                raise VarianError("Received bad response: {}".format(response))

        return pressure

    def set_emission_current(self, channel, current):
        """Set emission current in mA."""
        command = "53I{:01d}{:.3f}".format(channel, current)
        self._send_command(command)

    def read_emission_current(self, channel):
        command = "52I{:01d}".format(channel)
        response = self._send_command(command)

        try:
            current = float(response)
        except ValueError:
            # if the response cannot be cast to a float
            raise VarianError("Received bad response: {}".format(response))

        return current

    def close(self):
        self.s.close()


if __name__ == "__main__":

    g = VarianIonGauge(port="COM8")

    #g.set_emission_current(1, 9.99)
    #g.set_emission_current(2, 9.99)
    print(g.read_emission_current(1))
    print(g.read_emission_current(2))
    #g.set_emission_status(1, False)
    #g.set_emission_status(2, False)
    #g.set_emission_status(1, True)
    #g.set_emission_status(2, True)
    #import time
    # time.sleep(3)
    # print(g.read_emission_status(1))
    # print(g.read_emission_status(2))
    # print(g.read_pressure(1))
