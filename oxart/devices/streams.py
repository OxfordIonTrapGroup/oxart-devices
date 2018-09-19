""" Provides a pySerial-compatible wrapper for various channels, such as GPIB
and Ethernet, allowing drivers to be agnostic about the physical connection to
the device. """

import socket
import serial
import ipaddress
from oxart.devices.prologix_gpib.driver import GPIB


def address_args(parser, gpib=None):
    """ Add command-line arguments related to device addressing.

    :param gpib: if not None, the device supports a gpib interface. If
    isinstance(gpib, int) we use this as the default gpib address. NB devices
    with a GPIB address are assumed to be GPIB devices by get_stream.

    Note that we do not currently allow a "-p", "--port" argument for Ethernet
    devices, which would conflict with the port argument used by
    simple_network_server. In general, this doesn't seem to be that useful
    anyway.

    Use get_stream to return a connection to the device.
    """
    if gpib is not None:
        parser.add_argument("-d", "--device",
                            help="GPIB controller address")
        parser.add_argument("-gpib", "--gpib_addr",
                            help="device's GPIB address",
                            default=gpib if isinstance(gpib, int) else None)
    else:
        parser.add_argument("-d", "--device", help="device's address")


def get_stream(args, baudrate=115200, port=None, timeout=None):
    """ Returns a connection the device whose address is given in args.

    If args has a valid gpib address, we assume the device is a GPIB device.
    Note that we currently only support one device per GPIB controller.

    :param baudrate: baudrate to use for serial connections (default:115200)
    :param port: port to use for Ethernet connections
    :param timeout: timeout to use for read and write operations. Setting to
        None causes IO operations to block.
    """
    if hasattr(args, "gpib_addr") and isinstance(args.gpib_addr, int):
        port = 1234  # Port used by Prologix GPIB Ethernet controllers

    dev = None
    try:
        ipaddress.ip_address(args.device)
    except ValueError:
        if args.device.startswith("/dev/") \
           or args.device.lower().startswith("com"):
            dev = serial.Serial(args.device,
                                baudrate=baudrate,
                                timeout=timeout,
                                write_timeout=timeout)
    else:
        dev = Ethernet(args.device, port, timeout=timeout)
    if hasattr(args, "gpib_addr") and isinstance(args.gpib_addr, int):
        dev = GPIB(dev).get_stream(args.gpib_addr)
    return dev


class Ethernet:
    """ Simple pySerial-compatible wrapper for Ethernet sockets. """
    def __init__(self, addr, port, timeout=None):
        """
        :param timeout: timeout to use for read and write operations. Setting
        to None causes IO operations to block. For consistency with pySerail,
        we catch timeout exceptions; reads return b"".
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((addr, port))
        self.sock.settimeout(timeout)

    def read(self, size=1):
        """ Reads up to size bytes from the serial port. If a timeout is set it
        may return fewer characters than requested, otherwise it blocks until
        the requested number of bytes have been read.
        """
        try:
            return self.sock.recv(size)
        except socket.timeout:
            return b""

    def readline(self):
        """ Returns a line terminated with a single '\n' character.

        The final '\n' character and any immediately preceding '\r's are
        trimmed.

        This implementation is dumb and slow. We could use
        sock.makefile.readline instead, however that has some potential
        compatibility issues and does not work with non-blocking sockets.

        This implementation blocks, regardless of timeouts. That should be
        fixed at some point.
        """
        data = b""
        while True:
            char = self.read(1)
            if char == b"\n":
                break

            data += char
        return data.rstrip(b"\r")

    def write(self, data):
        """ Writes data and returns the number of bytes written.

        data must be a bytes-compatible type.
        """
        return self.sock.send(data)

    def close(self):
        self.sock.close()
