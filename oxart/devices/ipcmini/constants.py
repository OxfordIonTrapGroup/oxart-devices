"""Constants for use with IPCMini ion pump controller."""

import numpy as np

stx = b"\x02"
etx = b"\x03"
read = b"\x30"
write = b"\x31"
addr = b"\x80"

ack = b"\x06"
nack = b"\x15"
win_unknown = b"\x32"
data_error = b"\x33"  # wrong type or out of range
win_disabled = b"\x35"


def calculate_crc(bytes_):
    bytes_ = bytearray(bytes_)
    crc = np.bitwise_xor.reduce(bytes_)
    return "{:02X}".format(crc).encode()


def encode_read(win):
    return encode_message(win, read)


def encode_write(win, data):
    return encode_message(win, write, data)


def encode_message(win, com, data=None):
    msg = addr + "{:03}".format(win).encode() + com
    if data is not None:
        msg += data
    msg += etx
    msg += calculate_crc(msg)
    msg = stx + msg
    return msg


def decode_response(bytes_):
    stx_ = bytes_[:1]
    assert stx_ == stx
    addr_ = bytes_[1:2]
    assert addr_ == addr
    reply = bytes_[2:-3]
    etx_ = bytes_[-3:-2]
    assert etx_ == etx
    crc = bytes_[-2:]
    assert crc == calculate_crc(bytes_[1:-2])

    return reply


def decode_read_response(bytes_, win=None):
    reply = decode_response(bytes_)
    if win is not None:
        win_ = reply[:3]
        win_ = int(win_.decode())
        assert win_ == win
    data = reply[3:]

    return data.decode()


def decode_write_response(bytes_):
    """Return None if all OK."""
    code = decode_response(bytes_)
    check_return_code(code)


def check_return_code(code):
    if code == ack:
        return
    elif code == nack:
        raise CommandFailedError
    elif code == win_unknown:
        raise UnknownWindowError
    elif code == data_error:
        raise DataError
    elif code == win_disabled:
        raise WindowDisabledError
    else:
        raise UnknownReturnCodeError


# type N: numeric
# type A: alphanumeric
# type L: logical
windows = {
    "mode": {
        "win": 8,
        "type": "N",
        "docstring": "mode, allowed values are Serial/Remote/Local/LAN",
    },
    "hv_enable": {"win": 11, "type": "L"},
    "baud_rate": {
        "win": 108,
        "type": "N",
        "docstring": "baud rate, allowed values are 1200/2400/4800/9600",
    },
    "status": {"win": 205, "type": "N", "writable": False},
    "error_code": {"win": 206, "type": "N", "writable": False},
    "controller_model": {"win": 319, "type": "A"},
    "serial_number": {"win": 323, "type": "A"},
    "rs485_address": {"win": 503, "type": "N"},
    "serial_type": {"win": 504, "type": "L"},
    "pressure_units": {
        "win": 600,
        "type": "N",
        "docstring": "pressure units, allowed values are Torr/mbar/Pa",
    },
    "autostart": {"win": 601, "type": "L"},
    "protect": {"win": 602, "type": "L"},
    "fixed_step": {"win": 603, "type": "L"},
    "device_number": {"win": 610, "type": "N"},
    "max_power": {"win": 612, "type": "N"},
    "v_target": {
        "win": 613,
        "type": "N",
        "docstring": "target voltage from 3000-7000 V",
    },
    "i_protect": {
        "win": 614,
        "type": "N",
        "docstring": "protection current in uA from 1-10000 in integer steps",
    },
    "setpoint": {
        "win": 615,
        "type": "A",
        "docstring": "pressure setpoint in <pressure_units>",
    },
    "temp_power": {"win": 800, "type": "N", "writable": False},
    "temp_internal": {"win": 801, "type": "N", "writable": False},
    "setpoint_status": {"win": 804, "type": "L", "writable": False},
    "v_measured": {"win": 810, "type": "N", "writable": False},
    "i_measured": {"win": 811, "type": "A", "writable": False},
    "pressure": {"win": 812, "type": "A", "writable": False},
    "label": {"win": 890, "type": "A"},
}

lookups = {
    "mode": {0: "Serial", 1: "Remote", 2: "Local", 3: "LAN"},
    "baud_rate": {1: 1200, 2: 2400, 3: 4800, 4: 9600},
    "serial_type": {
        0: "RS232",
        1: "RS485",
    },
    "pressure_units": {0: "Torr", 1: "mbar", 2: "Pa"},
    "error_code": {
        0: "No Error",
        4: "Over Temperature",
        32: "Interlock Cable",
        64: "Short Circuit",
        128: "Protect",
    },
}
reverse_lookups = {
    name: {v: k for k, v in lookup.items()} for name, lookup in lookups.items()
}

floats = {"pressure", "setpoint", "i_measured"}


class UnknownWindowError(Exception):
    pass


class DataError(Exception):
    pass


class CommandFailedError(Exception):
    pass


class WindowDisabledError(Exception):
    pass


class UnknownReturnCodeError(Exception):
    pass
