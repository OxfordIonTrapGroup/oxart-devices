import serial
import struct
import time
import numpy as np


class Message:
    _id = 0
    param1 = 0
    param2 = 0
    source = 0x1
    dest = 0x50
    data = None

    def encode(self):
        if self.data:
            msg = struct.pack("HHBB", self._id, len(self.data), 0x80 | self.dest, self.source)
            msg = msg + self.data
        else:
            msg = struct.pack("HBBBB", self._id, self.param1, self.param2, self.dest, self.source)
        return msg

    def decode(self, msg):
        self._id, self.param1, self.param2, self.dest, self.source = struct.unpack("HBBBB", msg)


class MsgModIdentify(Message):
    _id = 0x0223
    def __init__(self, channel=0):
        self.param1 = channel

class MsgMotMoveHome(Message):
    _id = 0x0443
    def __init__(self, channel=0):
        self.param1 = channel

ID_MSG_MOVE_HOMED = 0x444
class MsgMotMoveHomed(Message):
    _id = ID_MSG_MOVE_HOMED

class MsgSetHomeParams(Message):
    _id = 0x0440
    def __init__(self, channel=0, direction=2, limit=1, velocity=0, offset=0):
        self.data = struct.pack("<HHHii", channel, direction, limit, velocity, offset)

class MsgMotMoveAbsolute(Message):
    _id = 0x0453
    def __init__(self, position=0, channel=0):
        self.data = struct.pack("<Hi", channel, position)

ID_MSG_MOVE_COMPLETED = 0x464
class MsgMotMoveCompleted(Message):
    _id = ID_MSG_MOVE_COMPLETED

class MsgMotSetVelParams(Message):
    _id = 0x0413
    def __init__(self, channel=0, vel_min=0, vel_max=0, acc=0):
        self.data = struct.pack("<Hiii", channel, vel_min, acc, vel_max)

class MsgMotSetPowerParams(Message):
    _id = 0x0426
    def __init__(self, channel=0, rest_factor=10, move_factor=30):
        """rest factor and move factor are the percentage of full drive power
        to use for holding and changing position respectively"""
        self.data = struct.pack("<HHH", channel, rest_factor, move_factor)


class APTDevice:
    def __init__(self, port):
        self.h = serial.Serial(port, 115200)

    def _send_message(self, message):
        msg = message.encode()
        self.h.write(msg)

    def _read_message(self):
        raw = self.h.read(6)
        msg = Message()
        msg.decode(raw)
        return msg

    def identify(self):
        self._send_message(MsgModIdentify())

    def set_home_params(self, velocity=0, offset=0):
        self._send_message(MsgSetHomeParams(velocity=velocity, offset=offset))

    def set_velocity_params(self, vel_min=0, vel_max=0, acc=0):
        msg = MsgMotSetVelParams(vel_min=vel_min, vel_max=vel_max, acc=acc)
        self._send_message(msg)

    def _wait_for_message(self, msg_id):
         while True:
            msg = self._read_message()
            if msg._id == msg_id:
                break

    def home(self):
        self._send_message(MsgMotMoveHome())
        self._wait_for_message(ID_MSG_MOVE_HOMED)

    def move(self, position):
        self._send_message(MsgMotMoveAbsolute(position))
        self._wait_for_message(ID_MSG_MOVE_COMPLETED)
        # Read out status payload
        self.h.read(14)

    def set_power_params(self, hold_power=0, move_power=0):
        assert hold_power >= 0 and hold_power <= 1
        assert move_power >= 0 and move_power <= 1
        hold_factor = int(hold_power * 100)
        move_factor = int(move_power * 100)
        msg = MsgMotSetPowerParams(rest_factor=hold_factor, move_factor=move_factor)
        self._send_message(msg)


class K10CR1(APTDevice):
    steps_per_degree = 136533
    def __init__(self, port, auto_home=True):
        super().__init__(port)

        self.set_velocity_params(acc=15020, vel_max=73300775)
        self.set_home_params(velocity=73300775, offset=546133)
        self.set_power_params(0.05, 0.3)

        if auto_home:
            self.home()

    def set_angle(self, angle):
        """Set angle in degrees"""
        angle_mu = int(angle * self.steps_per_degree)
        self.move(angle_mu)

    def ping(self):
        return True