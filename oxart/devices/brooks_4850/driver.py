from serial import serial_for_url
import struct
import time
import logging as log


CMD_SEND_ONE_DATA = 0x31
CMD_READ_VAR_INT16 = 0x61
CMD_WRITE_VAR_INT16 = 0x62
CMD_READ_VAR_CHAR = 0x63
CMD_WRITE_VAR_CHAR = 0x64
CMD_READ_GASINFO = 0x72


class CorruptionError(RuntimeError):
    pass


class Brooks4850:
    """Brooks 4850 mass flow controller driver"""
    def __init__(self, address):
        """ Connect to a Brookes flowmeter"""
        self.c = serial_for_url(address)
        # read in gas info from the device
        self.max_flow, self.gas_id, self.gas_density = self.read_gas_info()
        # set setpoint source select to RS232
        self._setpoint_source(0)

    def ping(self):
        try:
            read = self.read_flow()
        except IOError:  # serial errors inherit from this inbuilt
            return False
        if read is not None:
            return True
        else:
            return False

    def close(self):
        self.c.close()

    def _send_command(self, command, payload=None):

        data = struct.pack("B", command)

        if payload is not None:
            data += payload

            checksum = 0
            for c in data:
                checksum += c
            data += struct.pack("B", checksum & 0xFF)

        self.c.write(data)

    def _read_response(self, n_bytes):
        """Read a response from the device, waiting for
        n_bytes"""
        n_read = 0
        data = bytes()
        while(n_read < n_bytes):

            new_data = self.c.read(n_bytes)

            n_read += len(new_data)
            data += new_data

        command = data[0]
        if n_bytes == 1:
            return command, None

        # First byte is command
        # Last byte is checksum
        checksum_received = data[-1]
        checksum_calculated = 0
        for c in data[:-1]:
            checksum_calculated += c
        checksum_calculated &= 0xFF
        if checksum_calculated != checksum_received:
            # TODO: retry query
            raise CorruptionError("Bad checksum recieved")

        payload = data[1:-1]
        return command, payload

    def read_flow(self):
        """Read the current value of the flow meter
        in sccm (standard cubic centimeters per minute)
        for the selected gas"""
        self._send_command(CMD_SEND_ONE_DATA)
        command, payload = self._read_response(4)

        flow = struct.unpack(">H", payload)[0]
        real_flow = self.max_flow*flow/10000.
        return real_flow

    def read_temperature(self):
        """Read the temperature of the device"""
        self._send_command(CMD_READ_VAR_INT16, struct.pack("B", 15))
        command, payload = self._read_response(4)

        adc_temp = struct.unpack(">H", payload)[0]
        temperature = 100*((adc_temp/65535.) - 1 + (5/6.))
        return temperature

    def read_gas_info(self):
        """Read info about the selected gas"""
        self._send_command(CMD_READ_GASINFO)
        command, payload = self._read_response(8)

        max_flow, gas_id, gas_density = \
            struct.unpack(">HHH", payload)

        return max_flow, gas_id, gas_density

    def set_zero_offset(self):
        # NOTE THIS ISN'T WORKING CORRECTLY YET, I THINK - BUT NEEDS TESTING
        # WHEN FLOWING
        """Zero the flow controller reading to the current value"""
        self._send_command(CMD_WRITE_VAR_CHAR, struct.pack(">BB", 3, 1))
        command, payload = self._read_response(1)

        response = 1
        i = 0
        while response == 1:
            self._send_command(CMD_READ_VAR_CHAR, struct.pack("B", 3))
            command, payload = self._read_response(3)
            response = struct.unpack("B", payload)[0]
            print("Response = ")
            print(response)
            time.sleep(1)
            i += 1
            if i > 10:
                raise UserWarning("Time out - failed to zero flow meter")
                break

        if response == 3:
            raise ValueError("Zero point outside allowed range (+/-2%)")
        else:
            self._send_command(CMD_READ_VAR_INT16, struct.pack("B", 4))
            command, payload = self._read_response(4)
            new_zero = struct.unpack(">H", payload)[0]
            log.info("Flowmeter successfully zeroed, new zero = "
                     + str(new_zero))

    def reset_zero(self):
        """Reset the flow controller zero to the default value"""
        self._send_command(CMD_WRITE_VAR_CHAR, struct.pack(">BB", 3, 2))
        command, payload = self._read_response(1)

        self._send_command(CMD_READ_VAR_INT16, struct.pack("B", 4))
        command, payload = self._read_response(4)
        new_zero = struct.unpack(">H", payload)[0]
        log.info("Flowmeter zero reset to default value: " + str(new_zero))

    def _setpoint_source(self, source=0):
        """Selects source for set-point (0=RS232)"""
        self._send_command(CMD_WRITE_VAR_CHAR, struct.pack(">BB", 31, source))
        command, payload = self._read_response(1)

        self._send_command(CMD_READ_VAR_CHAR, struct.pack("B", 31))
        command, payload = self._read_response(3)

        if struct.unpack("B", payload)[0] == source:
            log.info("Set point source updated to input " + str(source))
        else:
            raise RuntimeError("Error updating set point source")

    def read_setpoint(self):
        """Read the current flow rate setpoint in sccm"""
        self._send_command(CMD_READ_VAR_INT16, struct.pack("B", 20))
        command, payload = self._read_response(4)

        setpoint_raw = struct.unpack(">H", payload)[0]
        setpoint = self.max_flow*setpoint_raw/65535.

        return setpoint

    def set_setpoint(self, setpoint):
        """set the current flow rate setpoint in sccm"""
        if setpoint > self.max_flow or setpoint < 0:
            raise ValueError("Setpoint {} is out of range (0,{})!".format(
                                 setpoint, self.max_flow))
        setpoint_raw = int(65535*setpoint/self.max_flow)
        self._send_command(CMD_WRITE_VAR_INT16,
                           struct.pack(">BH", 20, setpoint_raw))

        self._read_response(1)
        return setpoint


if __name__ == "__main__":
    log.basicConfig(level=log.INFO)
    f = Brooks4850("socket://10.255.6.178:9001")

    t = f.read_temperature()
    print("Temperature (C) = ", t)

    flow = f.read_flow()
    print("Flow rate (sccm) = ", flow*100.)

    max_flow, gas_id, gas_density = f.read_gas_info()
    print("max_flow = ", max_flow)
    print("gas_id = ", gas_id)
    print("gas_density = ", gas_density)

    setpoint = f.read_setpoint()
    print("setpoint = ", setpoint)

    f.set_setpoint(15000)
    setpoint = f.read_setpoint()
    print("setpoint = ", setpoint)

    print("ping:", f.ping())
    f.close()
    print("ping:", f.ping())
