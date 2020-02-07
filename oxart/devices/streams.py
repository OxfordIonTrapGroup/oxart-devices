import serial

from oxart.devices.prologix_gpib.driver import GPIB


def get_stream(device, baudrate=115200, port=None, timeout=None):
    """ Returns a pySerial-compatible interface to a hardware connection.

    Serial and Ethernet connections are handled by pySerial.serial_for_url()

    For GPIB controllers, the syntax is "gpib://<controller_device>-<port>"
    Where "<controller_device>" should be substituted for the hardware address
    of the GPIB controller and "<port>" is the GPIB port of the device. e.g.
    "gpib://socket://10.255.6.0:1234-0"

    :param baudrate: baudrate to use for serial connections (default:115200)
    :param timeout: timeout to use for read and write operations. Setting to
        None causes IO operations to block.
    """
    if not device.startswith("gpib://"):
        return serial.serial_for_url(device,
                                     baudrate=baudrate,
                                     timeout=timeout,
                                     write_timeout=timeout)

    controller_addr, gpib_port = device[7:].split('-')
    controller = GPIB(controller_addr, timeout=timeout)
    return controller.get_stream(int(gpib_port))
