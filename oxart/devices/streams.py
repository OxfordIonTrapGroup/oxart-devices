""" Provides a pySerial-compatible wrapper for various channels, such as GPIB
and Ethernet, allowing drivers to be agnostic about the physical connection to
the device. """

import socket


class Ethernet():
    """ Simple pySerial-compatible wrapper for Ethernet sockets. """
    def __init__(self, addr, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((addr, port))

    def read(self, size=1):
        """ Reads up to size bytes from the serial port. If a timeout is set it
        may return fewer characters than requested, otherwise it blocks until
        the requested number of bytes have been read.
        """
        return self.sock.recv(size)

    def readline(self):
        """ Returns a line terminated with a single '\n' character.

        The final '\n' character and any immediately preceding '\r's are
        trimmed.

        This implementation is dumb and slow. We could (should?) use
        sock.makefile.readline instead, however that has some potential
        compatibility issues.
        """
        data = b""
        while True:
            char = self.sock.recv(1)
            if char == b"\n":
                break

            data += char
        return data.rstrip(b"\r")

    def write(self, data):
        """ Writes data and returns the number of bytes written.

        data must be a bytes-compatible type.
        """
        return self.sock.send(data)
