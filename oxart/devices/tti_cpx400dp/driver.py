import logging
import socket
import time
from enum import Enum

from oxart.devices.streams import get_stream

logger = logging.getLogger(__name__)


class CPX400DP:
    """Driver for TTI CPX400DP power supply.

    This power supply has two independent outputs.
    Default TCP/IP port is 9221

    Voltage range: 0-60V
    Current range: 0-20A
    """

    def __init__(self, dmgr, device, port=9221):
        """Initialize connection to the power supply.

        Args:
            dmgr: Device manager instance
            device (str): IP address of the power supply
            port (int): TCP port number (default: 9221)
        """

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5.0)
        self.socket.connect((device, port))

    def _send_cmd(self, cmd):
        """Send a command to the power supply."""
        try:
            self.socket.send((cmd + "\n").encode("utf-8"))
            # time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error sending command '{cmd}': {e}")
            raise

    def _query(self, cmd):
        """Send a command and return the response."""
        self.socket.send((cmd + "\n").encode("utf-8"))
        time.sleep(0.1)
        return self.socket.recv(1024).decode("utf-8").strip()
        # except Exception as e:
        #     logger.error(f"Error querying with command '{cmd}': {e}")
        #     raise

    def close(self):
        """Close the connection to the power supply."""
        self.socket.close()
        del self.socket
        logger.debug("Connection closed")

    def ping(self):
        """Check if the device is responding correctly.

        Returns:
            bool: True if device responds correctly
        """
        try:
            ident = self.identify().split(",")
            return (ident[0].strip() == "THURLBY THANDAR"
                    and ident[1].strip() == "CPX400DP")
        except:
            return False

    def identify(self):
        """Get the device identification string.

        Returns:
            str: Device identification string
        """
        return self._query("*IDN?")

    def set_voltage(self, voltage, channel=1):
        """Set the voltage for the specified channel.

        Args:
            voltage (float): Voltage in volts (0-60V)
            channel (int): Output channel (1 or 2)
        """
        if not 0 <= voltage <= 60:
            raise ValueError("Voltage must be between 0 and 60V")
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        self._send_cmd(f"V{channel} {voltage}")

    def get_voltage_setpoint(self, channel=1):
        """Get the voltage setpoint for the specified channel.

        Args:
            channel (int): Output channel (1 or 2)

        Returns:
            float: Voltage setpoint in volts
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        return float(self._query(f"V{channel}?"))

    def get_voltage(self, channel=1):
        """Get the actual output voltage for the specified channel.

        Args:
            channel (int): Output channel (1 or 2)

        Returns:
            float: Measured output voltage in volts
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        return float(self._query(f"V{channel}O?")[:-1])

    def set_current(self, current, channel=1):
        """Set the current limit for the specified channel.

        Args:
            current (float): Current in amperes (0-20A)
            channel (int): Output channel (1 or 2)
        """
        if not 0 <= current <= 20:
            raise ValueError("Current must be between 0 and 20A")
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        self._send_cmd(f"I{channel} {current}")

    def get_current_setpoint(self, channel=1):
        """Get the current setpoint for the specified channel.

        Args:
            channel (int): Output channel (1 or 2)

        Returns:
            float: Current setpoint in amperes
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        return float(self._query(f"I{channel}?"))

    def get_current(self, channel=1):
        """Get the actual output current for the specified channel.

        Args:
            channel (int): Output channel (1 or 2)

        Returns:
            float: Measured output current in amperes
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        return float(self._query(f"I{channel}O?")[:-1])

    def set_output(self, state, channel=1):
        """Set the output state for the specified channel.

        Args:
            state (bool): True to enable output, False to disable
            channel (int): Output channel (1 or 2)
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        self._send_cmd(f"OP{channel} {1 if state else 0}")

    def get_output_state(self, channel=1):
        """Get the output state for the specified channel.

        Args:
            channel (int): Output channel (1 or 2)

        Returns:
            bool: True if output is enabled, False if disabled
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2")
        return bool(int(self._query(f"OP{channel}?")))

    def save_settings(self, location):
        """Save current settings to memory location.

        Args:
            location (int): Memory location (1-10)
        """
        if not 1 <= location <= 10:
            raise ValueError("Location must be between 1 and 10")
        self._send_cmd(f"SAV {location}")

    def recall_settings(self, location):
        """Recall settings from memory location.

        Args:
            location (int): Memory location (1-10)
        """
        if not 1 <= location <= 10:
            raise ValueError("Location must be between 1 and 10")
        self._send_cmd(f"RCL {location}")

    def get_status(self):
        """Get the power supply status.

        Returns:
            str: Status information string
        """
        return self._query("STATUS?")


if __name__ == "__main__":
    # Example usage
    try:
        # Create instance
        ps = CPX400DP("192.168.1.100")  # Replace with your IP

        # Print device info
        print(f"Connected to: {ps.identify()}")

        # Set up channel 1
        ps.set_voltage(12.0, channel=1)
        ps.set_current(1.0, channel=1)

        # Read back settings
        print(f"Voltage setting: {ps.get_voltage_setpoint(1)}V")
        print(f"Current setting: {ps.get_current_setpoint(1)}A")

        # Enable output
        ps.set_output(True, channel=1)

        # Read actual values
        print(f"Actual voltage: {ps.get_voltage(1)}V")
        print(f"Actual current: {ps.get_current(1)}A")

        # Disable output and close
        ps.set_output(False, channel=1)
        ps.close()

    except Exception as e:
        print(f"Error: {e}")
