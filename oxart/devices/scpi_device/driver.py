import time
import logging
import socket

logger = logging.getLogger(__name__)


class SCPIDevice:
    """
    Base class for *all* SCPI devices. Implements IEEE-488.2 standard functions.
    """
    def __init__(self, addr, port=5025, serial_number=None):
        # addr : IP address of *device*
        self.addr = addr
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.addr, port))

        # Store identity as a list of the comma separated fields returned
        self.idn = self.identity().split(',')

        # Some devices may not implement *IDN? in the same way, but most place
        # serial number in this field, allowing us to check that we have the
        # correct device
        if serial_number is not None:
            if self.idn[2] != serial_number:
                raise ValueError("Serial number {} did not match expected ({})"
                                 "".format(self.idn[2], serial_number))

    def close(self):
        self.sock.close()
        self.sock = None

    def send(self, cmd):
        data = cmd + "\n"
        self.sock.send(data.encode())

    def query(self, cmd):
        self.send(cmd)
        with self.sock.makefile() as f:
            response = f.readline().strip()
        return response

    def ping(self):
        # TODO - maybe check errors here?
        self.identity()
        return True

    # IEEE-488.2 functions
    # ====================

    def identity(self):
        # Returns ASCII data in 4 comma separated fields
        # Specification is vague, but usually follows
        # Field 1: manufacturer
        # Field 2: model number
        # Field 3: serial number
        # Field 4: firmware revision
        return self.query("*IDN?")

    def check_error(self):
        """Reads and clears the most recent error"""
        return self.query("*SYST:ERR?")

    def check_operation_complete(self):
        return bool(self.query("*OPC?"))

    def reset(self):
        """Reset values to default"""
        self.send("*RST")

