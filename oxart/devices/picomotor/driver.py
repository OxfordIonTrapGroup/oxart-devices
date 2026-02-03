import socket
import time
import logging

logger = logging.getLogger(__name__)


class PicomotorController:
    """Picomotor Controller Driver."""

    def __init__(self, device_ip):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(2)
        self.sock.connect((device_ip, 23))
        self.ip_addr = device_ip

        # dict containing commands as keys and a list with entries
        # [takes_channel, takes_argument, arg_min, arg_max]
        self.commands = {
            "*IDN?": [False, False],  # Identification string query
            "*RCL": [False, True, 0, 1],  # Recall parameters
            "*RST": [False, False],  # Reset instrument
            "AB": [False, False],  # Abort motion
            "AC": [True, True, 1, 200000],  # Set acceleration
            "AC?": [True, False],  # Get acceleration
            "DH": [True, True, -2147483648, 2147483647],  # Define home position
            "DH?": [True, False],  # Get home position
            "MC": [False, False],  # Motor check
            "MD?": [True, False],  # Get motion done status
            "MV": [True, True, "-", "+"],  # Move indefinitely
            "MV?": [True, False],  # Get motion direction
            "PA": [True, True, -2147483648, 2147483647],
            # Move to a target position
            "PA?": [True, False],  # Get destination position
            "PR": [True, True, -2147483648, 2147483647],  # Move relative
            "PR?": [True, False],  # Get destination position
            "QM": [True, True, 0, 3],  # Set motor type
            "QM?": [True, False],  # Get motor type
            "RS": [False, False],  # Reset the controller
            "SA": [False, True, 1, 31],  # Set controller address
            "SA?": [False, False],  # Get controller address
            "SC": [False, True, 0, 2],  # Scan RS-485 network
            "SC?": [False, False],  # Get RS-485 network controller addresses
            "SD?": [False, False],  # Get scan status
            "SM": [False, False],  # Save to non-volatile memory
            "ST": [True, False],  # Stop motion
            "TB?": [False, False],  # Get error message
            "TE?": [False, False],  # Get error number
            "TP?": [True, False],  # Get position
            "VA": [True, True, 1, 2000],  # Set velocity
            "VA?": [True, False],  # Get velocity
            "VE?": [False, False],  # Firmware version string query
            "XX": [False, False],  # Purge memory
            "ZZ": [False, True, None],  # Set configuration register
            "ZZ?": [False, False],  # Get configuration register
            "GATEWAY": [False, False],  # Default gateway address
            "GATEWAY?": [False, False],  # Default gateway address query
            "HOSTNAME": [False, True, None],  # Hostname
            "HOSTNAME?": [False, False],  # Hostname query
            "IPADDR": [False, True, None],  # IP address
            "IPADDR?": [False, False],  # IP address query
            "IPMODE": [False, True, 0, 1],  # IP mode
            "IPMODE?": [False, False],  # IP mode query
            "MACADDR?": [False, False],  # MAC address query
            "NETMASK": [False, True, None],  # Network mask address
            "NETMASK?": [False, False],  # Network mask address query
        }
        # dict containing all error code messages
        self.error_codes = {
            0: "NO ERROR DETECTED",
            3: "OVER TEMPERATURE SHUTDOWN",
            6: "COMMAND DOES NOT EXIST",
            7: "PARAMETER OUT OF RANGE",
            9: "AXIS NUMBER OUT OF RANGE",
            10: "EEPROM WRITE FAILED",
            11: "EEPROM READ FAILED",
            37: "AXIS NUMBER MISSING",
            38: "COMMAND PARAMETER MISSING",
            46: "RS-485 ETX FAULT DETECTED",
            47: "RS-485 CRC FAULT DETECTED",
            48: "CONTROLLER NUMBER OUT OF RANGE",
            49: "SCAN IN PROGRESS",
            100: "AXIS 1 MOTOR TYPE NOT DEFINED",
            200: "AXIS 2 MOTOR TYPE NOT DEFINED",
            300: "AXIS 3 MOTOR TYPE NOT DEFINED",
            400: "AXIS 4 MOTOR TYPE NOT DEFINED",
            101: "AXIS 1 PARAMETER OUT OF RANGE",
            201: "AXIS 2 PARAMETER OUT OF RANGE",
            301: "AXIS 3 PARAMETER OUT OF RANGE",
            401: "AXIS 4 PARAMETER OUT OF RANGE",
            108: "AXIS 1 MOTOR NOT CONNECTED",
            208: "AXIS 2 MOTOR NOT CONNECTED",
            308: "AXIS 3 MOTOR NOT CONNECTED",
            408: "AXIS 4 MOTOR NOT CONNECTED",
            110: "AXIS 1 MAXIMUM VELOCITY EXCEEDED",
            210: "AXIS 2 MAXIMUM VELOCITY EXCEEDED",
            310: "AXIS 3 MAXIMUM VELOCITY EXCEEDED",
            410: "AXIS 4 MAXIMUM VELOCITY EXCEEDED",
            111: "AXIS 1 MAXIMUM ACCELERATION EXCEEDED",
            211: "AXIS 2 MAXIMUM ACCELERATION EXCEEDED",
            311: "AXIS 3 MAXIMUM ACCELERATION EXCEEDED",
            411: "AXIS 4 MAXIMUM ACCELERATION EXCEEDED",
            114: "AXIS 1 MOTION IN PROGRESS",
            214: "AXIS 2 MOTION IN PROGRESS",
            314: "AXIS 3 MOTION IN PROGRESS",
            414: "AXIS 4 MOTION IN PROGRESS",
        }

        self._motor_detect_and_save_velocities()
        self.sock.recv(16)  # receiving nonsense first message
        logger.info("Connected to Picomotor Controller")

    def send_command(self, command, axis=None, argument=None):
        c = command

        assert command in self.commands, "Invalid Command"
        if self.commands[command][0]:
            assert self._is_valid_axis(axis), "Invalid Axis"
            c = str(axis) + c
        if self.commands[command][1]:
            assert self._is_valid_argument(command, argument), "Invalid Argument"
            c = c + str(argument)

        logger.info("Sending command: {}".format(c))
        self.sock.send(str.encode(c + "\n"))

    def receive(self):
        m = self.sock.recv(64).strip().decode()
        logger.info("Receiving: {}".format(m))
        return m

    def _is_valid_axis(self, ch):
        return ch in [1, 2, 3, 4]

    def _is_valid_argument(self, com, arg):
        if self.commands[com][2] is None:
            return True
        else:
            argmin = self.commands[com][2]
            argmax = self.commands[com][3]
            return argmin <= arg <= argmax or arg is argmin or arg is argmax

    def _motor_detect_and_save_velocities(self):
        self.send_command("MC")
        self.send_command("SM")

    def _error_code_query(self):
        self.send_command("TE?")
        return int(self.receive())

    # functions

    def wait_until_done(self, axis):
        while not self.motion_done(axis):
            time.sleep(0.1)

    def abort_motion(self):
        self.send_command("AB")

    def set_home(self, axis, home):
        self.send_command("DH", axis, home)

    def get_home(self, axis):
        self.send_command("DH?", axis)
        return int(self.receive())

    def set_velocity(self, axis, vel):
        self.send_command("VA", axis, vel)

    def get_velocity(self, axis):
        self.send_command("VA?", axis)
        return int(self.receive())

    def set_acceleration(self, axis, acc):
        self.send_command("AC", axis, acc)

    def get_acceleration(self, axis):
        self.send_command("AC?", axis)
        return int(self.receive())

    def motion_done(self, axis):
        self.send_command("MD?", axis)
        return bool(int(self.receive()))

    def move_absolute(self, axis, position):
        self.send_command("PA", axis, position)
        self.wait_until_done(axis)

    def move_relative(self, axis, distance):
        self.send_command("PR", axis, distance)
        self.wait_until_done(axis)

    def move_indefinitely(self, axis, direction):
        self.send_command("MV", axis, direction)

    def get_position(self, axis):
        self.send_command("TP?", axis)
        return int(self.receive())

    def stop_motion(self, axis):
        self.send_command("ST", axis)

    def reset_and_reboot(self):
        self.send_command("RS")

    def get_errors(self):
        errors = []
        errors.append(self._error_code_query())
        while errors[-1] != 0:
            errors.append(self._error_code_query())
        if len(errors) > 1:
            errors.pop(-1)
        return errors

    def get_error_message(self, error_code):
        if error_code in self.error_codes:
            return self.error_codes[error_code]

    def print_error_messages(self):
        errors = self.get_errors()
        for err in errors:
            print("{}: {}".format(err, self.get_error_message(err)))

    def get_device_ip(self):
        return self.ip_addr

    def get_identity(self):
        self.send_command("*IDN?")
        return self.receive()

    def close(self):
        self.sock.close()

    def ping(self):
        self.get_identity()
        return True
