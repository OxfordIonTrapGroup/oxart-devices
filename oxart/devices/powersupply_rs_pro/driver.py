import serial


class PowerSupply:

    def __init__(self, device):
        self.stream = serial.serial_for_url(device, 
            baudrate=9600, 
            timeout=1, 
            parity=serial.PARITY_NONE, 
            stopbits=serial.STOPBITS_ONE, 
            bytesize=serial.EIGHTBITS)

    def _send_cmd(self, msg):
        cmd = msg + "\r"
        self.stream.write(cmd.encode('utf-8'))

    def _read(self):
        return self.stream.read(20).decode()

    def set_current(self, current):
        """ 
        set current in A
        """
        if current < 0 or current > 5:
            raise ValueError("Current out of range")
        cmd = "ISET1:" + str(current)


    def set_voltage(self, voltage):
        """ 
        set voltage in V
        """
        if voltage < 0 or voltage > 30:
            raise ValueError("Voltage out of range")
        cmd = "VSET1:" + str(voltage)
        self._send_cmd(cmd)
    
    def get_current(self):
        cmd = "IOUT1?"
        self._send_cmd(cmd)
        return self._read()[:-1]

    def get_voltage(self):
        cmd = "VOUT1?"
        self._send_cmd(cmd)
        return self._read()[:-1]

    def switch_on(self):
        cmd = "OUT1"
        self._send_cmd(cmd)

    def switch_off(self):
        cmd = "OUT0"
        self._send_cmd(cmd)

    def close(self):
        self.stream.close()

    def status(self):
        cmd = "STATUS?"
        self._send_cmd(cmd)
        binary_rep = format(ord(self.stream.read(20)[:-1]), '08b')
        print("Status: ", binary_rep)
        if binary_rep[0] == "0":
            print("CC mode")
        else:
            print("CV mode")
        
        if binary_rep[6] == "0":
            print("Output off")
        else:
            print("Output on")


if __name__ == "__main__":
    PowerSupply = PowerSupply("socket://10.255.6.188:9001")

    PowerSupply.status()

