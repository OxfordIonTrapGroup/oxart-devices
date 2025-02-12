import serial
import socket
import select
import hart_protocol as hart
import numpy as np
import struct
import time
import sys
import logging as log


CMD_READ_UNIQUE_IDENTIFIER = 0
CMD_READ_PRIMARY_VARIABLE = 1
CMD_READ_CURRENT_AND_ALL_DYNAMIC_VARIABLES = 3
CMD_READ_UNIQUE_IDENTIFIER_ASSOCIATED_WITH_TAG = 11
CMD_READ_MESSAGE = 12
CMD_SET_PRIMARY_VARIABLE_LOWER_RANGE_VALUE = 37
CMD_RESET_CONFIGURATION_CHANGED_FLAG = 38
CMD_PERFORM_MASTER_RESET = 42
CMD_READ_ADDITIONAL_TRANSMITTER_STATUS = 48
CMD_READ_DYNAMIC_VARIABLE_ASSIGNMENT = 50
CMD_READ_GAS_NAME = 150
CMD_READ_GAS_INFO = 151
CMD_READ_FULL_SCALE_FLOW_RANGE = 152
CMD_READ_STANDARD_TEMPERATURE_AND_PRESSURE = 190
CMD_WRITE_STANDARD_TEMPERATURE_AND_PRESSURE = 191
CMD_READ_OPERATIONAL_FLOW_SETTINGS = 193
CMD_SELECT_PRESSURE_APPLICATION_NUMBER = 194
CMD_SELECT_GAS_CALIBRATION_NUMBER = 195
CMD_SELECT_FLOW_UNIT = 196
CMD_SELECT_TEMPERATURE_UNIT = 197
CMD_SELECT_PRESSURE_OR_FLOW_CONTROL = 199
CMD_READ_SETPOINT_SETTINGS = 215
CMD_SELECT_SETPOINT_SOURCE = 216
CMD_SELECT_SOFTSTART = 218
CMD_WRITE_LINEAR_SOFTSTART_RAMP_VALUE = 219
CMD_READ_PID_VALUES = 220
CMD_WRITE_PID_VALUES = 221
CMD_READ_VALVE_RANGE_AND_OFFSET = 222
CMD_WRITE_VALVE_RANGE_AND_OFFSET = 223
CMD_GET_VALVE_OVERRIDE_STATUS = 230
CMD_SET_VALVE_OVERRIDE_STATUS = 231
CMD_READ_SETPOINT = 235
CMD_WRITE_SETPOINT = 236
CMD_READ_VALVE_CONTROL_VALUE = 237
CMD_READ_PRESSURE_ALARM = 243
CMD_WRITE_PRESSURE_ALARM = 244
CMD_READ_ALARM_ENABLE_SETTING = 245
CMD_WRITE_ALARM_ENABLE_SETTING = 246
CMD_READ_FLOW_ALARM = 247
CMD_WRITE_FLOW_ALARM = 248

#The unit dictionaries below don't contain all units listed in the flowmeter's manual (yet).
# Dictionaries for flow rate units
flow_rate_code_to_str_dict = {17: "l/min", 19: "m^3/h", 24: "l/s", 28: "m^3/s", 70: "g/s", 71: "g/min", 72: "g/h", 73: "kg/s", 74: "kg/min",
                        75: "kg/h", 131: "m^3/min", 138: "l/h", 170: "ml/s", 171: "ml/min", 172: "ml/h"}
flow_rate_str_to_code_dict = dict([reversed(i) for i in flow_rate_code_to_str_dict.items()])

# Dictionary for flow reference conditions
flow_reference_dict = {0: "Normal (273.15 Kelvin/1013.33 mbar)", 1: "Standard (user-defined through separate command)", 2: "As defined at calibration"}

# Dictionaries for density units
density_code_to_str_dict = {91: "g/cm^3", 92: "kg/m^3", 95: "g/ml", 96: "kg/l", 97: "g/l"}
density_str_to_code_dict = dict([reversed(i) for i in density_code_to_str_dict.items()])

# Dictionaries for temperature units
temperature_code_to_str_dict = {32: "deg Celsius", 33: "deg Fahrenheit", 35: "Kelvin"}
temperature_str_to_code_dict = dict([reversed(i) for i in temperature_code_to_str_dict.items()])

# Dictionaries for pressure units
pressure_code_to_str_dict = {5: "PSI", 7: "bar", 8: "mbar", 11: "Pa", 12: "kPa", 13: "Torr", 14: "Std Atmosphere", 232: "atm",
                            238: "bar", 241: "Counts", 242: "%", 244: "mTorr" }
pressure_str_to_code_dict = dict([reversed(i) for i in pressure_code_to_str_dict.items()])

# Dictionary to look up assignment of dynamic variables
dynamic_variables_dict = {0: "Flow rate", 1: "Temperature", 2: "Pressure"}

# Dictionaries for valve override
valve_override_code_to_str_dict = {0: "off", 1: "open", 2: "close", 4: "manual"}
valve_override_str_to_code_dict = dict([reversed(i) for i in valve_override_code_to_str_dict.items()])



# Create a dictionary to decode packed-ASCII messages
# First, append all entries from "@" to "_" to the dictionary
packed_ascii_to_char_dict = {}
for i in range(0x1F + 1):
    packed_ascii_to_char_dict[i] = chr(i + 64)
# Next, append all entries from (SPACE) to "?" to the dictionary
for i in range(32):
    packed_ascii_to_char_dict[0x20 + i] = chr(i + 32)

# Also create the reversed dictionary to encode packed-ASCII messages
char_to_packed_ascii_dict = dict([reversed(i) for i in packed_ascii_to_char_dict.items()])



class CorruptionError(RuntimeError):
    pass


class BrooksSLA5850:
    """Brooks SLA5850 mass flow controller driver"""
    def __init__(self, ip_address, port, device_tag = "50200285"):
        """ Connect to a Brookes flowmeter"""
        self.flowmeter = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect to the ES device using a Raw TCP socket
        self.flowmeter.connect((ip_address, port))
        print("Connected to the flowmeter")
        self.device_identifier = self.read_unique_identifier_associated_with_tag(device_tag)
        self.long_frame_address = self.construct_long_address_from_device_id(self.device_identifier)
        print("Created long frame address of flowmeter")
        # Set flow unit to l/min
        # This also sets the flow reference condition to "as calibrated", if no other reference code is provided
        self.select_flow_unit("l/min")
        # Set setpoint source to 3, i.e. digital
        self.select_setpoint_source(3)
        # Make sure that valve override is off
        self.set_valve_override_status("off")

    def read_response(self):
        """ Read the response from the flowmeter.
        Return format is: command (int), status_1 (int), status_2 (int), payload (bytes object)"""

        # Read response of the flowmeter
        # The "ready" variable is used to make sure that the recv() function is only called if data is available
        ready = select.select([self.flowmeter], [], [], 1)
        if ready[0]:
            message = self.flowmeter.recv(1024)
        else:
            raise CorruptionError("Device is not responding")
        ready = select.select([self.flowmeter], [], [], 1)
        while ready[0]:
            message += self.flowmeter.recv(1024)
            ready = select.select([self.flowmeter], [], [], 1)

        # Decode the response, i.e., return command, status info and payload
        # Skip preamble characters
        # The start character of an "acknowledge" message from slave to master is 0x86
        j = 0
        while message[j] != 0x86:
                j += 1
        # Also skip the start and address characters (6 bytes in total, assuming long frame addressing)
        j += 6
        # The command byte is the one after the address characters
        # and the command is represented by an integer value
        command = message[j]
        j += 1
        # Next byte: byte count character (indicates number of status and data bytes in the response message)
        byte_count = message[j]
        j += 1
        # The next two bytes are the status characters
        status_1 = message[j]
        j += 1
        status_2 = message[j]
        j += 1
        # Extract the payload consisting of (byte_count - 2) bytes
        if byte_count > 2:
            payload = message[j:(j + byte_count - 2)]
            j += byte_count - 2
        else:
            payload = []

        # Calculate checksum and compare to checksum byte at the end of the message
        checksum_message = message[j]
        checksum_calculated = self.calculate_longitudinal_parity(message[:j], message_type = 'acknowledge')
        if checksum_message != checksum_calculated:
            raise CorruptionError("Bad checksum received")

        return command, status_1, status_2, payload

    def send_command(self, command_number, payload = None, data_format_string = None):
        """Returns a message from the given input parameters that has the correct format to be sent
           to the flowmeter.
        """

        message = struct.pack("B", 0xFF)
        for n in range(4):
            message += struct.pack("B", 0xFF) # Preamble characters
        message += struct.pack("B", 0x82) # Start character (for long frame addressing and Start-Of-Text)
        # Add long frame address to message
        message += self.long_frame_address
        # Add command
        message += struct.pack("B", command_number)
        # Initialize empty bytes object to store payload
        payload_bytes = b''
        if payload is None:
            size_payload = 0
            #message += struct.pack("B", size_payload) # this is the "byte count char", indicating the length of the payload in bytes
        else:
            size_payload = struct.calcsize(data_format_string)
            j = 0
            if size_payload > 24:
                raise ValueError("Payload is larger than 24 bytes")
            if data_format_string[0] in ['<', '>', '!', '=', '@']:
                j = 1
                byte_order_string = data_format_string[0]
            else:
                byte_order_string = ''
            for i in range(len(data_format_string) - j):
                # Adding information on the byte order to every data format string is important correctly encode the data
                format_char = str(byte_order_string) + str(data_format_string[i + j])
                # Count number of "I"s in data_format_string, and subtract 1 from size_payload for each "I"
                # This is because the standard size of an unsigned int is 4 bytes, while the SLA5853 expects 3 bytes
                if format_char == "I":
                    payload_bytes += struct.pack("I", payload[i])[0:3]
                    size_payload = size_payload - 1
                else:
                    payload_bytes += struct.pack(format_char, payload[i])

        message += struct.pack("B", size_payload)
        message += payload_bytes

        # The longitudinal parity (XOR of all message characters) is used here as the checksum
        checksum = self.calculate_longitudinal_parity(message)
        message += struct.pack("B", checksum)

        #print(message)
        self.flowmeter.send(message)

    def read_unique_identifier_associated_with_tag(self, tag_as_string):
        """Return the unique identifier associated with the tag of the flowmeter."""
        tag = hart.tools.pack_ascii(tag_as_string)
        self.flowmeter.send(hart.universal.read_unique_identifier_associated_with_tag(tag))
        response = self.read_response()

        # Check if returned command is the expected one
        if response[0] != CMD_READ_UNIQUE_IDENTIFIER_ASSOCIATED_WITH_TAG:
            raise CorruptionError("Incorrect command returned")

        # Raise potential error messages in status info
        #self.decode_status_info(response[1], response[2])

        # Extract the device id from the payload
        device_id = response[3][9:12]

        return device_id

    def calculate_longitudinal_parity(self, message, message_type = 'start_of_text'):
        """Calculates the longitudinal parity, which is used as the checksum in the communication
        with the SLA5853 flow meter, of the given message (excluding the preamble characters).

        The longitudinal parity is the exclusive-or of all message bytes (characters from the start
        character up to just before the checksum). To avoid counting the preamble characters, the function
        searches for the first occurrence of either 82 (hex, start character for 'start_of_text' message, i.e.
        from master to slave) or 86 ('acknowledge' message, i.e. slave to master) and only starts applying XOR
        from that location onwards."""

        # First, make sure to skip the preamble characters
        j = 0
        if message_type == 'start_of_text':
            while message[j] != 0x82:
                j += 1
        elif message_type == 'acknowledge':
            while message[j] != 0x86:
                j += 1
        else:
            raise ValueError("message_type must be either 'start_of_text' or 'acknowledge' ")

        message_length = len(message) - j
        checksum = message[j] ^ message[j + 1]
        for i in range(message_length - 2):
            checksum = checksum ^ message[i + 2 + j]

        return checksum

    def ping(self):
        """Return true if flowmeter reacts to commands (more specifically, the read_flow_rate_and_temperature
        command). Return false otherwise."""
        try:
            read = self.read_flow_rate_and_temperature()
        except IOError:  # serial errors inherit from this inbuilt
            return False
        if read is not None:
            return True
        else:
            return False

    def decode_status_info(self, status_1, status_2):
        """ Decode error messages in the two status bytes of a slave-to-master message.
        Returns status_1 because for some commands, it can contain additional information. """

        # Transform status bytes into binary arrays to extract bitwise-encoded information
        status_1_array = np.array([[status_1]], dtype = np.uint8)
        status_1_binary = np.unpackbits(status_1_array)
        status_2_array = np.array([[status_2]], dtype = np.uint8)
        status_2_binary = np.unpackbits(status_2_array)

        # If the second status byte is 0 and bit 7 of the first status byte is 1, the communication failed.
        # The type of communication error is encoded in status byte 1.
        if status_2 == 0 and status_1_binary[0] == 1:
            # Go through status byte 1 bit by bit and print all error messages where the bit is of value 1
            error_messages = [ "Parity error", "Overrun error", "Framing error", "Checksum error", "Reserved", "Rx Buffer Overflow"]
            for i in range(7):
                if status_1_binary[i + 1] == 1:
                    print(error_messages[i])
                    raise CorruptionError("Communication failed")
        # If the second status byte is non-zero, communication did not fail.
        # In that case: status_1 contains command execution info, status_2 contains info on device status
        else:
            # First, print command execution info
            if status_1 == 2:
                raise CorruptionError("Invalid selection")
            elif status_1 == 3:
                raise ValueError("Passed parameter too large")
            elif status_1 == 4:
                raise ValueError("Passed parameter too small")
            elif status_1 == 5:
                raise CorruptionError("Incorrect byte count")
            elif status_1 == 6:
                raise CorruptionError("Transmitter specific command error")
            elif status_1 == 7:
                raise CorruptionError("In Write-Protect Mode")
            elif status_1 == 16:
                raise CorruptionError("Access Restricted")
            elif status_1 == 32:
                raise CorruptionError("Device is busy")
            elif status_1 == 64:
                raise CorruptionError("Command Not Implemented")
            elif status_1 > 7 and status_1 < 16:
                raise CorruptionError("Command-specific error")
            # Next, print device status info
            # Go through status byte 2 bit by bit and print all error messages where the bit is of value 1
            error_messages_2 = ["Device malfunction", "Configuration changed", "Cold start", "More status available", "Primary variable analog output fixed", "Primary variable analog output saturated", "Non primary variable out of range", "Primary variable out of range"]
            for i in range(8):
                if status_2_binary[i] == 1:
                    print(error_messages_2[i])
            # Print more status info if available
            if status_2_binary[3] == 1:
                self.read_additional_transmitter_status()

    def construct_long_address_from_device_id(self, device_id, manufacturer_id = 10, device_type_code = 100):
        """ Returns the long frame address of a device with the given identifiers.
            Format of the long frame address is:
            Byte 0: Manufacturer_id OR 0x80
            Byte 1: device type code (100 in decimal for Brooks SLA Series)
            Bytes 2 to 4: device identifier
         """

        long_frame_address = struct.pack(">B", manufacturer_id | 0x80)
        long_frame_address += struct.pack(">B", device_type_code)
        for i in range(len(device_id)):
            long_frame_address += struct.pack(">B", device_id[i])

        return long_frame_address

    def read_process_gas_type(self, gas_selection_code = 1):
        """Return the gas type corresponding to the given gas selection code (int between 1 and 6)."""

        self.send_command(CMD_READ_GAS_NAME, [gas_selection_code], ">B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        # Check if the expected gas selection code was returned
        if gas_selection_code != response[3][0]:
            raise CorruptionError("Incorrect gas selection code returned")
        # The remaining payload of the response contains name or chemical formula of the gas, encoded in ASCII
        # Decode the gas type and return it as a string
        #gas_type_string_length = len(response[3])-1
        gas_type_string = "".join(chr(i) for i in response[3][1:])

        return gas_type_string

    def select_gas_calibration(self, calibration_number = 1):
        """Select a gas calibration from the available calibrations.
        Refer to the Product/Calibration Data Sheet(s) shipped with each device to determine the proper
        gas calibration number for the desired gas/flow conditions.
        """
        if calibration_number < 1 or calibration_number > 6:
            raise ValueError("Undefined calibration number.")

        self.send_command(CMD_SELECT_GAS_CALIBRATION_NUMBER, [calibration_number], ">B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        # Check if the expected gas selection code was returned
        returned_calibration_number = response[3][0]
        if returned_calibration_number != calibration_number:
            raise CorruptionError("Incorrect calibration number returned")

        print("Set calibration number of SLA5853 flowmeter to ", returned_calibration_number)

    def select_temperature_unit(self, temperature_unit = "Kelvin"):
        """Sets the temperature unit to either deg Celsius, deg Fahrenheit or Kelvin.
        The corresponding temperature unit codes are:
        32: deg Celsius
        33: deg Fahrenheit
        35: Kelvin
        """
        if temperature_unit not in temperature_str_to_code_dict:
            raise ValueError("Undefined temperature unit. Choose either deg Celsius, deg Fahrenheit or Kelvin.")

        temperature_unit_code = temperature_str_to_code_dict[temperature_unit]

        self.send_command(CMD_SELECT_TEMPERATURE_UNIT, [temperature_unit_code], ">B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        # Check if the expected gas selection code was returned
        returned_temp_unit_code = response[3][0]
        if temperature_unit_code != returned_temp_unit_code:
            raise CorruptionError("Incorrect temperature unit code returned")

        print("Set temperature unit of SLA5853 flowmeter to " + temperature_unit)

    def read_setpoint(self):
        """Returns current setpoint value in % of full scale and in selected unit.

        The selected unit for the flowmeter used for comet, lab 3, with serial number 06C43200327 is "ml/min",
        which corresponds to flow rate unit code 171. Many more flow rate units are available; to use this code with
        a different device and a potentially different unit, add the respective code and unit description in the code below.
        """
        self.send_command(CMD_READ_SETPOINT)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        setpoint_in_percent = struct.unpack(">f", response[3][1:5])[0]
        selected_unit_code = response[3][5]
        if selected_unit_code in flow_rate_code_to_str_dict:
            selected_unit_string = flow_rate_code_to_str_dict[selected_unit_code]
        else:
            raise ValueError("Undefined flow unit code")
        setpoint_in_selected_unit = struct.unpack(">f", response[3][6:10])[0]

        return setpoint_in_percent, setpoint_in_selected_unit, selected_unit_string

    def write_setpoint(self, setpoint_value, unit_code = 57):
        """Sets flow setpoint to the input parameter setpoint_value, given either in percent (default, unit_code = 57) of
        full scale or selected unit (unit_code = 250).
        """
        self.send_command(CMD_WRITE_SETPOINT, [unit_code, setpoint_value], ">Bf")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        returned_percent_unit_code = response[3][0]
        # Check if the returned percent unit code is correct (should be 57)
        if returned_percent_unit_code != 57:
            raise CorruptionError("Returned incorrect percent unit code")
        new_setpoint_in_percent = struct.unpack(">f", response[3][1:5])[0]
        selected_unit = response[3][5]
        if selected_unit in flow_rate_code_to_str_dict:
            selected_unit_string = flow_rate_code_to_str_dict[selected_unit]
        else:
            raise ValueError("Undefined flow unit code")
        new_setpoint_in_selected_unit = struct.unpack(">f", response[3][6:10])[0]

        return new_setpoint_in_percent, new_setpoint_in_selected_unit, selected_unit_string

    def read_full_scale_flow_range(self, gas_select_code = 1):
        """Returns full scale flow range for the selected gas type (gas_select_code is int between 1 and 6, if the device has
            only been calibrated for one type of gas it's always 1).

        The selected unit for the flowmeter used for comet, lab 3, with serial number 06C43200327 is "ml/min",
        which corresponds to flow rate unit code 171. Many more flow rate units are available; to use this code with
        a different device and a potentially different unit, add the respective code and unit description in the code below.
        """
        self.send_command(CMD_READ_FULL_SCALE_FLOW_RANGE, [gas_select_code], "<B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        selected_unit_code = response[3][0]
        if selected_unit_code in flow_rate_code_to_str_dict:
            selected_unit_string = flow_rate_code_to_str_dict[selected_unit_code]
        else:
            raise ValueError("Undefined flow unit code")
        flow_rate_range_in_selected_unit = struct.unpack(">f", response[3][1:5])[0]

        return flow_rate_range_in_selected_unit, selected_unit_string

    def read_standard_temperature_and_pressure_range(self):
        """Read the standard temperature and pressure values from the device’s memory.
        The standard temperature and pressure are reference values which can be set by the user """

        self.send_command(CMD_READ_STANDARD_TEMPERATURE_AND_PRESSURE)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        temperature_unit_code = response[3][0]
        if temperature_unit_code in temperature_code_to_str_dict:
            temperature_unit_string = temperature_code_to_str_dict[temperature_unit_code]
        else:
            raise ValueError("Undefined temperature unit code")
        standard_temperature = struct.unpack(">f", response[3][1:5])[0]
        pressure_unit_code = response[3][5]
        if pressure_unit_code in pressure_code_to_str_dict:
            pressure_unit_string = pressure_code_to_str_dict[pressure_unit_code]
        else:
            raise ValueError("Undefined pressure unit code")
        standard_pressure = struct.unpack(">f", response[3][6:10])[0]

        return standard_temperature, temperature_unit_string, standard_pressure, pressure_unit_string

    def write_standard_temperature_and_pressure(self, standard_temp, standard_pressure, temp_unit = "Kelvin", pressure_unit = "Pa"):
        """Write the standard temperature and pressure values into the device's memory and return the newly set values,
        together with their units (as strings).

        The standard temperature and pressure are reference values which can be set by the user and which are used
        in the conversion of flow units. """

        # Check if the given temperature unit is defined, and if yes, find the corresponding unit code.
        if temp_unit not in temperature_str_to_code_dict:
            raise ValueError("Undefined temperature unit. Choose either deg Celsius, deg Fahrenheit or Kelvin.")
        temperature_unit_code = temperature_str_to_code_dict[temp_unit]
        # Check if the given pressure unit is defined, and if yes, find the corresponding unit code.
        if pressure_unit not in pressure_str_to_code_dict:
            raise ValueError("Undefined pressure unit")
        pressure_unit_code = pressure_str_to_code_dict[pressure_unit]

        self.send_command(CMD_WRITE_STANDARD_TEMPERATURE_AND_PRESSURE, [temperature_unit_code, standard_temp, pressure_unit_code, standard_pressure], "<BfBf")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        temperature_unit_code = response[3][0]
        if temperature_unit_code in temperature_code_to_str_dict:
            temperature_unit_string = temperature_code_to_str_dict[temperature_unit_code]
        else:
            raise ValueError("Undefined temperature unit code returned")
        standard_temperature_new = struct.unpack(">f", response[3][1:5])[0]
        pressure_unit_code = response[3][5]
        if pressure_unit_code in pressure_code_to_str_dict:
            pressure_unit_string = pressure_code_to_str_dict[pressure_unit_code]
        else:
            raise ValueError("Undefined pressure unit code returned")
        standard_pressure_new = struct.unpack(">f", response[3][6:10])[0]

        return standard_temperature_new, temperature_unit_string, standard_pressure_new, pressure_unit_string

    def read_flow_settings(self):
        """Read the operational settings from the device. These settings consist of the selected gas number,
            the selected flow reference condition, the selected flow unit and the selected temperature unit.
        """
        self.send_command(CMD_READ_OPERATIONAL_FLOW_SETTINGS)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        selected_gas_number = response[3][0]
        selected_flow_reference = response[3][1]
        if selected_flow_reference in flow_reference_dict:
            selected_flow_reference_string = flow_reference_dict[selected_flow_reference]
        else:
            raise ValueError("Undefined flow unit code")
        selected_flow_unit = response[3][2]
        if selected_flow_unit in flow_rate_code_to_str_dict:
            selected_flow_unit_string = flow_rate_code_to_str_dict[selected_flow_unit]
        else:
            raise ValueError("Undefined flow unit code")
        selected_temperature_unit = response[3][3]
        if selected_temperature_unit in temperature_code_to_str_dict:
            selected_temperature_unit_string = temperature_code_to_str_dict[selected_temperature_unit]
        else:
            raise ValueError("Undefined temperature unit code")

        return selected_gas_number, selected_flow_reference_string, selected_flow_unit_string, selected_temperature_unit_string

    def select_flow_unit(self, selected_flow_unit_string, selected_flow_ref_code = 2):
        """Select a flow unit and the flow reference condition. The selected flow unit will be used in the conversion of flow data """

        # Check if the given flow unit is valid and if yes, find the corresponding unit code
        if selected_flow_unit_string not in flow_rate_str_to_code_dict:
            raise ValueError("Undefined flow rate unit.")
        flow_rate_unit_code = flow_rate_str_to_code_dict[selected_flow_unit_string]
        # Check if given reference code is valid
        if selected_flow_ref_code not in flow_reference_dict:
            raise ValueError("Undefined reference code. Choose either 0 (273.15 Kelvin/1013.33 mbar), 1 (user-defined) or 2 (as calibrated).")

        self.send_command(CMD_SELECT_FLOW_UNIT, [selected_flow_ref_code, flow_rate_unit_code], "BB")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        # Check if the expected flow reference code was returned
        returned_flow_ref_code = response[3][0]
        if returned_flow_ref_code != selected_flow_ref_code:
            raise CorruptionError("Incorrect flow reference code returned")
        # Check if the expected flow rate unit code was returned
        returned_flow_rate_unit_code = response[3][1]
        if returned_flow_rate_unit_code != flow_rate_unit_code:
            raise CorruptionError("Incorrect flow rate unit code returned")

        print("Set flow reference to " + flow_reference_dict[returned_flow_ref_code] + " and flow rate unit to " + flow_rate_code_to_str_dict[returned_flow_rate_unit_code])

    def read_setpoint_settings(self):
        """Read the setpoint related settings from the device.

        The settings contain the setpoint source indication:
        Setpoint source code = 1: analog 0 - 5 V / 0 - 10 V / 0 - 20 mA
        Setpoint source code = 2: analog 4 - 20 mA
        Setpoint source code = 3: digital
        the type of softstart and the softstart ramp. """

        self.send_command(CMD_READ_SETPOINT_SETTINGS)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        setpoint_source_selection_code = response[3][0]
        # According to the device's manual, the returned setpoint span should always be 1.0
        setpoint_span = struct.unpack(">f", response[3][1:5])[0]
        # According to the device's manual, the returned setpoint offset should always be 0.0
        setpoint_offset = struct.unpack(">f", response[3][5:9])[0]
        softstart_selection_code = response[3][9]
        softstart_ramp_value = struct.unpack(">f", response[3][10:14])[0]

        return setpoint_source_selection_code, setpoint_span, setpoint_offset, softstart_selection_code, softstart_ramp_value

    def select_setpoint_source(self, setpoint_source_code):
        """Select the setpoint source to be used as setpoint input. Possible setpoint source codes and their meanings are:

        1, 2: Analog Input and Output type configured during production
        3: digital
        10: Analog Input and Output 0-5 V
        11: Analog Input and Output 1-5 V
        20: Analog Input and Output 0-20 mA
        21: Analog Input and Output 4-20 mA """

        # Check if setpoint source code is valid
        if setpoint_source_code not in [1, 2, 3, 10, 11, 20, 21]:
            raise ValueError("Setpoint source code undefined.")

        self.send_command(CMD_SELECT_SETPOINT_SOURCE, [setpoint_source_code], "B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        returned_setpoint_source_code = response[3][0]
        # Check if input and returned setpoint source codes match
        if returned_setpoint_source_code != setpoint_source_code:
            raise ValueError("Incorrect setpoint source code returned.")
        print("Set setpoint source code to " + str(returned_setpoint_source_code))

    def read_valve_settings(self):
        """Read the Valve Range and Valve Offset values from the device.

        The settings are 24-bit unsigned integers used to fine tune the D/A converter for the valve control.
        The numbers are dimensionless and sized to the range of 0 to 62500. 100% flow is achieved with the number
        valve offset + valve range. Also, the sum of both should not be over 62500. """

        self.send_command(CMD_READ_VALVE_RANGE_AND_OFFSET)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        valve_range = int.from_bytes(response[3][0:3],'big',signed=False)
        valve_offset = int.from_bytes(response[3][3:6],'big',signed=False)
        # Check if the sum of valve range and valve offset is <= 62500
        if (valve_range + valve_offset) > 62500:
            raise ValueError("Sum of valve range and offset is too high (> 62500)")

        return valve_range, valve_offset

    def write_valve_settings(self, valve_range = 0, valve_offset = 0):
        """Write the Valve Offset values into the device. The Valve Range is not used in devices of the SLA Enhanced Series,
        therefore, this value should always be set to 0.

        The settings are 24-bit unsigned integers used to fine tune the D/A converter for the valve control.
        The numbers are dimensionless and sized to the range of 0 to 62500. 100% flow is achieved with the number
        valve offset + valve range. Also, the sum of both should not be over 62500 """

        # Check if valve range + offset is within a valid range (i.e., >= 0 and <= 62500)
        range_and_offset_sum = valve_range + valve_offset
        if range_and_offset_sum < 0 or range_and_offset_sum > 62500:
            raise ValueError("Invalid range and/or offset value. Range + offset needs to be <= 62500")

        self.send_command(CMD_WRITE_VALVE_RANGE_AND_OFFSET, [valve_range, valve_offset], "II")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        returned_valve_range = int.from_bytes(response[3][0:3],'big',signed=False)
        returned_valve_offset = int.from_bytes(response[3][3:6],'big',signed=False)
        # Check if the sum of valve range and valve offset is <= 62500
        if (returned_valve_range + returned_valve_offset) > 62500:
            raise ValueError("Sum of returned valve range and offset is too high (> 62500)")

        return returned_valve_range, returned_valve_offset

    def read_gas_info(self, gas_selection_code = 1):
        """Read the density of the selected gas (gas selection code is int between 1 and 6), the operational flow range and
        the reference temperature and pressure for the flow range.

        The flow range equals the volume flow in engineering units at 100% as calibrated. The reference temperature
        and pressure are the conditions at which the volume flow is specified."""

        self.send_command(CMD_READ_GAS_INFO, [gas_selection_code], "B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        # Check if the expected gas selection code was returned
        if gas_selection_code != response[3][0]:
            raise CorruptionError("Incorrect gas selection code returned")
        density_unit_code = response[3][1]
        if density_unit_code in density_code_to_str_dict:
            density_unit_string = density_code_to_str_dict[density_unit_code]
        else:
            raise ValueError("Undefined density unit code")
        gas_density = struct.unpack(">f", response[3][2:6])[0]
        reference_temperature_unit_code = response[3][6]
        if reference_temperature_unit_code in temperature_code_to_str_dict:
            reference_temperature_unit_string = temperature_code_to_str_dict[reference_temperature_unit_code]
        else:
            raise ValueError("Undefined temperature unit code")
        reference_temperature = struct.unpack(">f", response[3][7:11])[0]
        reference_pressure_unit_code = response[3][11]
        if reference_pressure_unit_code in pressure_code_to_str_dict:
            reference_pressure_unit_string = pressure_code_to_str_dict[reference_pressure_unit_code]
        else:
            raise ValueError("Undefined pressure unit code")
        reference_pressure = struct.unpack(">f", response[3][12:16])[0]
        reference_flow_rate_unit_code = response[3][16]
        if reference_flow_rate_unit_code in flow_rate_code_to_str_dict:
            reference_flow_rate_unit_string = flow_rate_code_to_str_dict[reference_flow_rate_unit_code]
        else:
            raise ValueError("Undefined flow rate unit code")
        reference_flow_range = struct.unpack(">f", response[3][17:21])[0]

        return gas_density, density_unit_string, reference_temperature, reference_temperature_unit_string, reference_pressure, reference_pressure_unit_string, reference_flow_range, reference_flow_rate_unit_string

    def read_pid_controller_values(self):
        """Return PID controller parameters in the order K_p, K_i, K_d """

        self.send_command(CMD_READ_PID_VALUES)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        k_p = struct.unpack("f", response[3][0:4])[0]
        k_i = struct.unpack("f", response[3][4:8])[0]
        k_d = struct.unpack("f", response[3][8:12])[0]

        return k_p, k_i, k_d

    def write_pid_controller_values(self, k_p_new, k_i_new, k_d_new):
        """Set PID controller parameters to the values given by k_p_new, k_i_new, k_d_new and
        return the new values in the same order if successful. """

        self.send_command(CMD_WRITE_PID_VALUES, [k_p_new, k_i_new, k_d_new], "fff")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        k_p = struct.unpack("f", response[3][0:4])[0]
        k_i = struct.unpack("f", response[3][4:8])[0]
        k_d = struct.unpack("f", response[3][8:12])[0]

        return k_p, k_i, k_d

    def close_connection(self):
        """Closes connection to flowmeter."""
        self.flowmeter.close()
        # print("Disconnected from flowmeter")

    def read_flow_rate_and_temperature(self):
        """Returns flow rate and temperature, together with the respective units.

        The underlying command is command #3, "Read current and all dynamic variables".
        In case of the Brooks SLA5853 flowmeter (type MFC), there are two dynamic variables, the primary
        and the secondary one. """

        self.send_command(CMD_READ_CURRENT_AND_ALL_DYNAMIC_VARIABLES)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        # Read analog output current (mA) or voltage (V)
        analog_output = struct.unpack(">f", response[3][0:4])[0]
        # Read primary variable unit code (for SLA5853, primary variable = flow rate)
        prim_var_unit_code = response[3][4]
        # Create string to describe primary variable unit
        if prim_var_unit_code in flow_rate_code_to_str_dict:
            prim_var_unit_string = flow_rate_code_to_str_dict[prim_var_unit_code]
        else:
            raise ValueError("Undefined flow rate unit")
        # Read value of primary variable
        prim_variable = struct.unpack(">f", response[3][5:9])[0]
        # Read secondary variable unit code (for SLA5853, secondary variable = temperature)
        scd_var_unit_code = response[3][9]
        # Create string to describe secondary variable unit
        if scd_var_unit_code in temperature_code_to_str_dict:
            scd_var_unit_string = temperature_code_to_str_dict[scd_var_unit_code]
        else:
            raise ValueError("Undefined temperature unit")
        # Read value of secondary variable
        scd_variable = struct.unpack(">f", response[3][10:14])[0]



        return prim_variable, prim_var_unit_string, scd_variable, scd_var_unit_string

    def zero_flow_rate_sensor(self):
        """Zero sensor associated with flow rate measurement.
        Only use this command when there is no flow through the device!"""

        self.send_command(CMD_SET_PRIMARY_VARIABLE_LOWER_RANGE_VALUE)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        print("Flow rate sensor has been zeroed.")

    def reset_configuration_changed_flag(self):
        """Resets the configuration changed response code, bit #6 of the transmitter status byte.
        Primary master devices, address ‘1’, should only issue this command after the configuration
        changed response code has been detected and acted upon. """

        self.send_command(CMD_RESET_CONFIGURATION_CHANGED_FLAG)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        print("Configuration-changed flag has been reset.")

    def reset_flowmeter(self):
        """Reset the device’s microprocessor. The device will respond first and then perform the master reset. """

        self.send_command(CMD_PERFORM_MASTER_RESET)
        print("Flowmeter will be reset now.")

    def read_dynamic_variable_assignments(self):
        """Read transmitter variable numbers assigned to primary and secondary variable and find their definitions. """

        self.send_command(CMD_READ_DYNAMIC_VARIABLE_ASSIGNMENT)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        prim_var_code = response[3][0]
        scd_var_code = response[3][1]
        # Find definitions of both variable codes in dictionary
        if prim_var_code in dynamic_variables_dict:
            prim_var_description = dynamic_variables_dict[prim_var_code]
        else:
            raise ValueError("Undefined variable number 1")
        if scd_var_code in dynamic_variables_dict:
            scd_var_description = dynamic_variables_dict[scd_var_code]
        else:
            raise ValueError("Undefined variable number 2")

        return prim_var_description, scd_var_description

    def read_valve_control_value(self):
        """Read the current valve control value. The valve control value is a dimensionless number in the range
        from 0 to 62500. It represents the value sent to the D/A-converter used to control the valve """

        self.send_command(CMD_READ_VALVE_CONTROL_VALUE)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        valve_control_value = int.from_bytes(response[3][0:3],'big',signed=False)
        # Check if valve control value is <= 62500
        if valve_control_value > 62500:
            raise ValueError("Invalid valve control value")

        return valve_control_value

    def get_valve_override_status(self):
        """Get the current valve override status from the device. The valve override status can be set to
        either off (no valve override), close, open or manual. """

        self.send_command(CMD_GET_VALVE_OVERRIDE_STATUS)
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        valve_override_code = response[3][0]
        # Get the description of the returned override code from the dictionary
        valve_override_description = valve_override_code_to_str_dict[valve_override_code]

        return valve_override_description

    def set_valve_override_status(self, valve_override_status = "off"):
        """Set the valve override status of the device. The valve override status can be set to
        either off (no valve override), close, open or manual. """

        # Get the code corresponding to the valve override status description given
        valve_override_code = valve_override_str_to_code_dict[valve_override_status]

        self.send_command(CMD_SET_VALVE_OVERRIDE_STATUS, [valve_override_code], ">B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        returned_valve_override_code = response[3][0]
        # Get the description of the returned override code from the dictionary
        returned_valve_override_description = valve_override_code_to_str_dict[returned_valve_override_code]

        return returned_valve_override_description

    def select_softstart_mode(self, softstart_selection_code = 0):
        """Select the softstart type to be used by the device. The softstart mode can be set to either
        disabled or time. When Time is selected, then the Software Ramp value (see Command #219)
        will be the time required to ramp to a new setpoint expressed in seconds. """

        # Check if the given softstart selection code is valid (it must be either 0 or 4)
        if softstart_selection_code not in [0, 4]:
            raise ValueError("Invalid softstart selection code")

        self.send_command(CMD_SELECT_SOFTSTART, [softstart_selection_code], ">B")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        returned_softstart_selection_code = response[3][0]
        # Check if the input and returned softstart selection codes match
        if returned_softstart_selection_code != softstart_selection_code:
            raise CorruptionError("Incorrect softstart selection code returned")

        if returned_softstart_selection_code == 0:
            print("Switched softstart off.")
        elif returned_softstart_selection_code == 4:
            print("Switched to linear softstart")

        return returned_softstart_selection_code

    def write_linear_softstart_ramp_time(self, ramp_time):
        """Write the linear softstart ramp time (in seconds) into the device’s memory. """

        self.send_command(CMD_WRITE_LINEAR_SOFTSTART_RAMP_VALUE, [ramp_time], ">f")
        response = self.read_response()
        self.decode_status_info(response[1], response[2])
        returned_ramp_time = struct.unpack("<f", response[3][0:4])[0]

        return returned_ramp_time

    def read_additional_transmitter_status(self):
        """Retrieve additional transmitter status information. This function is supposed to be called whenn byte 2 of the status bytes
        contains the message "More status available".  """

        self.send_command(CMD_READ_ADDITIONAL_TRANSMITTER_STATUS)
        response = self.read_response()
        add_status_byte_1 = response[3][0]
        add_status_byte_2 = response[3][1]
        add_status_byte_3 = response[3][2]
        add_status_byte_4 = response[3][3]

        # Transform additional status info bytes into binary arrays to extract bitwise-encoded information
        add_status_1_array = np.array([[add_status_byte_1]], dtype = np.uint8)
        add_status_1_binary = np.unpackbits(add_status_1_array)
        add_status_2_array = np.array([[add_status_byte_2]], dtype = np.uint8)
        add_status_2_binary = np.unpackbits(add_status_2_array)
        add_status_3_array = np.array([[add_status_byte_3]], dtype = np.uint8)
        add_status_3_binary = np.unpackbits(add_status_3_array)
        add_status_4_array = np.array([[add_status_byte_4]], dtype = np.uint8)
        add_status_4_binary = np.unpackbits(add_status_4_array)

        start_string = "Additional status info: "

        # Decode information in additional status byte 1
        if add_status_1_binary[0] == 1:
            print(start_string + "Program memory corrupt")
        if add_status_1_binary[1] == 1:
            print(start_string + "RAM test failure")
        if add_status_1_binary[3] == 1:
            print(start_string + "Non-volatile memory failure")
        if add_status_1_binary[5] == 1:
            print(start_string + "Internal power supply failure")

        # Decode information in additional status byte 2
        if add_status_2_binary[6] == 0:
            print(start_string + "Setpoint deviation (controller error) disabled")
        if add_status_2_binary[7] == 1:
            print(start_string + "Temperature out of limits")

        # Decode information in additional status byte 3
        if add_status_3_binary[0] == 1:
            print(start_string + "Low flow alarm")#
        if add_status_3_binary[1] == 1:
            print(start_string + "High flow alarm")
        if add_status_3_binary[2] == 1:
            print(start_string + "Totalizer overflow")
        if add_status_3_binary[3] == 1:
            print(start_string + "Low pressure alarm")
        if add_status_3_binary[4] == 1:
            print(start_string + "High pressure alarm")
        if add_status_3_binary[5] == 1:
            print(start_string + "Valve drive out of limits")
        if add_status_3_binary[7] == 1:
            print(start_string + "Device calibration due")

        # Decode information in additional status byte 4
        if add_status_4_binary[0] == 1:
            print(start_string + "Device overhaul due")
        if add_status_4_binary[2] == 1:
            print(start_string + "Device overhaul due")







if __name__ == "__main__":


    f = BrooksSLA5850("10.179.22.99", 9001)
    # device_tag = "50200285"
    # device_identifier = f.read_unique_identifier_associated_with_tag(device_tag)
    # address = f.construct_long_address_from_device_id(device_identifier)

    # gas_density, density_unit, ref_temp, temp_unit, ref_pressure, pressure_unit, ref_flow, flow_unit = f.read_gas_info()
    # print("Gas density = ", gas_density, density_unit)
    # print("Reference temperature = ", ref_temp, temp_unit)
    # print("Reference pressure = ", ref_pressure, pressure_unit)
    # print("Reference flow range = ", ref_flow, flow_unit)

    # # Read current flow and temperature
    # current_flow, current_flow_unit, current_temp, current_temp_unit = f.read_flow_rate_and_temperature()
    # print("Temperature = ", current_temp, current_temp_unit)
    # print("Flow rate = ", current_flow, current_flow_unit)

    # # Read current setpoint
    # setpoint_in_percent, setpoint_in_sel_unit, setpoint_unit = f.read_setpoint()
    # print("Setpoint = ", setpoint_in_sel_unit, setpoint_unit)

    # Change setpoint
    new_setpoint_in_nlpm = 9
    f.write_setpoint(new_setpoint_in_nlpm, flow_rate_str_to_code_dict["l/min"])
    # f.write_setpoint(100, 57)
    setpoint_in_percent, setpoint_in_sel_unit, setpoint_unit = f.read_setpoint()
    print("New setpoint = ", setpoint_in_sel_unit, setpoint_unit)
    print(f.read_valve_settings())

    # print(f.get_valve_override_status())

    # while True:
    #     current_flow, current_flow_unit, current_temp, current_temp_unit = f.read_flow_rate_and_temperature()
    #     print("Temperature = ", current_temp, current_temp_unit)
    #     print("Flow rate = ", current_flow, current_flow_unit)

    # f.close_connection()








