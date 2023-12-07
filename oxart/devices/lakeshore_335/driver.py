""" Driver for Lake Shore Cryogenics Model 335 Temperature controllers """

from oxart.devices.streams import get_stream


class LakeShore335:

    def __init__(self, device):
        self.stream = get_stream(device)
        assert self.ping()

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def get_temp(self, input="A"):
        """ Returns the temperature of an input channel as a float in Kelvin
        : param input: either "A" or "B"
        """
        self.stream.write("KRDG? {}\n".format(input).encode())
        return float(self.stream.readline())

    def ping(self):
        idn = self.identify().split(',')
        return idn[0:2] == ['LSCI', 'MODEL335']

    def get_manual_heater_output(self, output=1):
        """ Returns the output power/current of the heater, scale 0-100%.
        Must set heater mode to open loop first.
        : param output: either 1 or 2 for heater channels
        : return: output power/current of the heater, scale 0-100%
        """
        self.stream.write("MOUT? {}\n".format(output).encode())
        return float(self.stream.readline())

    def set_manual_heater_output(self, value, output=1):
        """ Sets the output power/current of the heater, scale 0-100%. Depends on
        display setting in heater_setup function. Must set heater mode to open loop
        first.

        : param value: 0 - 100 %
        : param output: either 1 or 2 for heater channels
        : return: output, value
        """
        self.stream.write("MOUT {},{}\n".format(output, value).encode())
        return output, value

    def get_heater_output(self, output=1):
        """ Returns the output power/current of the heater, scale 0-100%.
        : param output: either 1 or 2 for heater channels
        : return: output power/current of the heater, scale 0-100%
        """
        self.stream.write("HTR? {}\n".format(output).encode())
        return float(self.stream.readline())

    def get_heater_mode(self, output=1):
        """ Returns the output mode of the heater
        : param output: either 1 or 2 for heater channels
        : return: <mode>, <input>, <powerup enable>
        """
        self.stream.write("OUTMODE? {}\n".format(output).encode())
        return float(self.stream.readline())

    def set_heater_mode(self, mode, channel=1, output=1, powerup_enable=0):
        """ Set the output mode of the heater
        : param mode: Control mode: 0 = Off, 1 = PID, 2 = Zone, 3 = Open Loop,
                                    4 = Monitor out, 5 = Warmup Supply
        : param output: either 1 or 2 for heater channels
        : param input: input to use for control: 0 = None, 1 = A, 2 = B
        : param powerup_enable: Specifies whether the output remains on or shuts off
                                after power cycle.
                                0 = powerup enable off, 1 = powerup enable on.
        : return: output, mode, channel, powerup_enable
        """
        self.stream.write("OUTMODE {},{},{},{}\n".format(output, mode, channel,
                                                         powerup_enable).encode())
        return output, mode, channel, powerup_enable

    def get_heater_range(self, output=1):
        """ Returns the heater range
        : param output: either 1 or 2 for heater channels
        : return: For Outputs 1 and 2 in Current mode: 0 = Off, 1 = Low, 2 = Medium,
                  3 = High
                  For Output 2 in Voltage mode: 0 = Off, 1 = On
        """
        self.stream.write("RANGE? {}\n".format(output).encode())
        return float(self.stream.readline())

    def set_heater_range(self, htr_range, output=1):
        """ Returns the heater range
        : param output: either 1 or 2 for heater channels
        : return: For Outputs 1 and 2 in Current mode: 0 = Off, 1 = Low, 2 = Medium,
                  3 = High
                  For Output 2 in Voltage mode: 0 = Off, 1 = On
        """
        self.stream.write("RANGE {},{}\n".format(output, htr_range).encode())
        return output, htr_range

    def get_pid(self, output=1):
        """ Returns the PID settings
        : param output: either 1 or 2 for heater channels
        : return: <P value>, <I value>, <D value>
        """
        self.stream.write("PID? {}\n".format(output).encode())
        return self.stream.readline().decode()

    def set_pid(self, p, i, d, output=1):
        """ Set PID paramaters
        : param output: either 1 or 2 for heater channels
        : param p: Proportional 0.1 to 1000.
        : param i: Integral 0.1 to 1000.
        : param d: Derivative 0 to 200.
        : return: output, p, i, d
        """
        self.stream.write("PID {},{},{},{}\n".format(output, p, i, d).encode())
        return output, p, i, d

    def get_setpoint(self, output=1):
        """ Get the temeperature set point for PID
        : param output: either 1 or 2 for heater channels
        : return: Temperature of PID setpoint (K)
        """
        self.stream.write("SETP? {}\n".format(output).encode())
        return float(self.stream.readline())

    def set_setpoint(self, value, output=1):
        """ Set the temeperature set point for PID
        : param output: either 1 or 2 for heater channels
        : param value: temperature (K)
        : return: output, value
        """
        self.stream.write("SETP {},{}\n".format(output, value).encode())
        return output, value

    def heater_setup(self, out_type, htr_res, I_max, I_max_user, display, output=1):
        """ Configures the heater
        : param output: either 1 or 2 for heater channels
        : param out_type: Output type (Output 2 only): 0=Current, 1=Voltage
        : param htr_res: Heater Resistance Setting: 1 = 25 Ohm, 2 = 50 Ohm
        : param I_max_user: Specifies the maximum heater output current if
                            max current is set to User Specified. (A)
        : param I_max: Specifies the maximum heater output current:
                       0 = User Specified, 1 = 0.707 A, 2 = 1 A, 3 = 1.141 A,
                       4 = 1.732 A
        : param display: Specifies whether the heater output displays in current or
                         power (current mode only). Valid entries: 1 = current,
                         2 = power
        : return: output, out_type, htr_res, I_max, I_max_user, display
        """
        self.stream.write("HTRSET {},{},{},{},{},{}\n".format(
            output, out_type, htr_res, I_max, I_max_user, display).encode())
        return output, out_type, htr_res, I_max, I_max_user, display

    def get_heater_setup(self, output=1):
        """ Returns the current configuration of the heater
        : param output: either 1 or 2 for heater channels
        see above 'heater_setup' function for return meanings
        : return: output, out_type, htr_res, I_max, I_max_user, display
        """
        self.stream.write("HTRSET? {}\n".format(output).encode())
        out = self.stream.readline().decode().split(',')
        return out

    def close(self):
        self.stream.close()
