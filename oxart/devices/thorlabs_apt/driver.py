import sys
import serial
import struct
import time
import numpy as np
import logging
from enum import IntEnum

logger = logging.getLogger(__name__)

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
        self.data_len = None
        if self.dest & 0x80:
            # data packet to follow
            self.data_len = self.param1 + (self.param2 << 8)


class MsgModIdentify(Message):
    _id = 0x0223
    def __init__(self, channel=0):
        self.param1 = channel

class MsgMotMoveHome(Message):
    _id = 0x0443
    def __init__(self, channel=0):
        self.param1 = channel
ID_MSG_MOVE_HOMED = 0x444

class MsgSetHomeParams(Message):
    _id = 0x0440
    def __init__(self, channel=0, direction=2, limit=1, velocity=0, offset=0):
        self.data = struct.pack("<HHHii", channel, direction, limit, velocity, offset)

class MsgMotMoveAbsolute(Message):
    _id = 0x0453
    def __init__(self, position=0, channel=0):
        self.data = struct.pack("<Hi", channel, position)

class MsgMotMoveRelative(MsgMotMoveAbsolute):
    _id = 0x0448

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

class MsgMotMoveStop(Message):
    _id = 0x0465
    param2 = 1
ID_MSG_MOVE_STOPPED = 0x0466

class MsgSetChanEnableState(Message):
    _id = 0x0210
    def __init__(self, channel=1, enable=True):
        self.param1 = channel
        self.param2 = 1 if enable else 2

class MsgMotResumeEndOfMoveMsgs(Message):
    _id = 0x046C

class MsgMotReqDcStatus(Message):
    _id = 0x0490
ID_MSG_DCSTATUSUPDATE = 0x0491

class MsgMotAckDcStatus(Message):
    _id = 0x0492

class MsgMotReqDcStatusBits(Message):
    _id = 0x0429
ID_MSG_DCSTATUSBITS = 0x042A

class Status(IntEnum):
    HW_LIM_FORWARD = 0x01
    HW_LIM_REVERSE = 0x02
    MOVING_FORWARD = 0x10
    MOVING_REVERSE = 0x20
    JOGGING_FORWARD = 0x40
    JOGGING_REVERSE = 0x80
    MOVING_HOME = 0x200
    HOMED = 0x400
    TRACKING = 0x1000
    SETTLED = 0x2000
    POSITION_ERROR = 0x1000000
    ENABLED = 0x80000000

class MsgHwReqInfo(Message):
    _id = 0x0005
ID_MSG_HW_GET_INFO = 0x0006


class _APTDevice:
    def __init__(self, port):
        self.h = serial.Serial(port, 115200, write_timeout=0.1)
        self._update_counter = 0

    def _send_message(self, message):
        msg = message.encode()
        # print("tx: {}".format(msg.hex()))
        self.h.write(msg)

    def _read_message(self):
        raw = self.h.read(6)
        # print("rx: {}".format(raw.hex()))
        msg = Message()
        msg.decode(raw)
        if msg.data_len:
            msg.data = self.h.read(msg.data_len)
        return msg

    def _wait_for_message(self, msg_id):
         while True:
            msg = self._read_message()
            if msg._id in [ID_MSG_MOVE_COMPLETED,
                           ID_MSG_MOVE_STOPPED,
                           ID_MSG_MOVE_HOMED]:
                self._update_counter += 1
                if self._update_counter > 25:
                    self._update_counter = 0
                    self.ack_status_update()
            if msg._id == msg_id:
                return msg

    def identify(self):
        self._send_message(MsgModIdentify())

    def set_channel_enable(self, enable=True):
        self._send_message(MsgSetChanEnableState(channel=1,enable=enable))

    def set_home_params(self, velocity=0, offset=0):
        self._send_message(MsgSetHomeParams(velocity=velocity, offset=offset))

    def set_velocity_params(self, vel_min=0, vel_max=0, acc=0):
        msg = MsgMotSetVelParams(vel_min=vel_min, vel_max=vel_max, acc=acc)
        self._send_message(msg)

    def get_status(self):
        self._send_message(MsgMotReqDcStatus())
        msg = self._wait_for_message(ID_MSG_DCSTATUSUPDATE)
        chan, position, velocity, _, status = struct.unpack("=HIHHI", msg.data)
        return chan, position, velocity, status

    def get_status_bits(self):
        self._send_message(MsgMotReqDcStatusBits())
        msg = self._wait_for_message(ID_MSG_DCSTATUSBITS)
        _, status = struct.unpack("=HI", msg.data)
        return status

    def _wait_until_stopped(self, poll_time=0.1):
        count = 0
        while True:
            # sleep at start of loop to allow it to get moving
            # 40ms appears to be very near the minimum
            time.sleep(poll_time)

            if not self.is_moving():
                # require 2 consecutive readings at rest
                count += 1
                if count > 1:
                    break
            else:
                count = 0

    def is_moving(self):
        moving = (Status.MOVING_HOME
                  + Status.MOVING_FORWARD
                  + Status.MOVING_REVERSE
                  + Status.JOGGING_FORWARD
                  + Status.JOGGING_REVERSE)
        status = self.get_status_bits()
        return (status & moving) != 0

    def resume_end_of_move_messages(self):
        self._send_message(MsgMotResumeEndOfMoveMsgs())

    def ack_status_update(self):
        self._send_message(MsgMotAckDcStatus())

    def home(self):
        logger.debug("Homing...")
        self._send_message(MsgMotMoveHome())
        self._wait_for_message(ID_MSG_MOVE_HOMED)
        logger.debug("Homed")

    def move(self, position):
        self._send_message(MsgMotMoveAbsolute(position))
        self._wait_for_message(ID_MSG_MOVE_COMPLETED)

    def move_relative(self, position_change):
        self._send_message(MsgMotMoveRelative(position_change))
        self._wait_for_message(ID_MSG_MOVE_COMPLETED)

    def set_power_params(self, hold_power=0, move_power=0):
        assert hold_power >= 0 and hold_power <= 1
        assert move_power >= 0 and move_power <= 1
        hold_factor = int(hold_power * 100)
        move_factor = int(move_power * 100)
        msg = MsgMotSetPowerParams(rest_factor=hold_factor, move_factor=move_factor)
        self._send_message(msg)

    def stop(self):
        self._send_message(MsgMotMoveStop())
        self._wait_for_message(ID_MSG_MOVE_STOPPED)

    def close(self):
        self.h.close()

    def ping(self):
        try:
            self.get_status()
        except:
            return False
        return True


class _APTRotation(_APTDevice):
    """Generic class of rotation mounts"""
    def __init__(self, port, auto_home=True):
        super().__init__(port)

        self.setup()
        if auto_home:
            self.home()

    def setup(self):
        self.set_channel_enable(True)
        self.set_velocity_params(acc=self.max_acc, vel_max=self.max_vel)
        self.set_home_params(velocity=self.homing_vel, offset=self.offset)
        self.set_power_params(0.05, 0.3)

    def home(self):
        super().home()
        self._last_angle_mu = None

    def set_angle(self, angle, check_position=True, auto_retry=0, **kwargs):
        """
        Set angle in degrees.

        Optional parameters:
        check_position - verify that position is set correctly
        auto_retry - number of retries to achieve correct position, default 0
        """
        angle = angle % 360
        angle_mu = int(angle * self.steps_per_degree)
        self.move(angle_mu)
        self._last_angle_mu = angle_mu

        if check_position:
            try:
                self.check_angle_mu(wait=False, **kwargs)
            except ValueError as e:
                if auto_retry > 0:
                    self.set_angle(angle, check_position=check_position,
                        auto_retry=auto_retry-1, **kwargs)
                else:
                    raise

    def get_angle(self):
        """Get current angle in degrees"""
        angle_mu = self._get_angle_mu()
        angle = float(angle_mu)/self.steps_per_degree
        angle = angle % 360
        return angle

    def check_angle_mu(self, acceptable_error=40, **kwargs):
        """Check currently set angle against stored value"""
        if self._last_angle_mu == None:
            # nothing to check against
            return

        angle_mu = self._get_angle_mu(**kwargs)
        angle_mu = angle_mu % int(360*self.steps_per_degree)
        if abs(self._last_angle_mu - angle_mu) > acceptable_error:
            raise ValueError("Last angle set does not match current angle",
                self._last_angle_mu, angle_mu)
        else:
            # if we're off by an acceptable amount, store the actual value
            self._last_angle_mu = angle_mu

    def _get_angle_mu(self, wait=True):
        """Get current angle in steps"""
        if wait:
            self._wait_until_stopped()
        _, angle_mu, _, _ = self.get_status()
        return angle_mu



class K10CR1(_APTRotation):
    steps_per_degree = 136533
    max_acc = 15020
    max_vel = 73300775
    homing_vel = 7300775
    offset = 546133
    def set_angle(self, angle):
        """Set angle in degrees"""
        # These drivers are slow, so need to intelligently choose rotation
        # direction if we can to minimize rotation distance.
        angle = angle % 360
        angle_mu = int(angle * self.steps_per_degree)

        if self._last_angle_mu:
            # We know our last position, so we can do a relative move
            delta = angle_mu - self._last_angle_mu
            for offset in [360*self.steps_per_degree, -360*self.steps_per_degree]:
                if abs(delta+offset) < abs(delta):
                    delta += offset
            self.move_relative(delta)
        else:
            self.move(angle_mu)
        self._last_angle_mu = angle_mu


class _KBD101(_APTRotation):
    """This will not work if instantiated directly"""
    def setup(self):
        self.req_hw_info()
        super().setup()

    def req_hw_info(self):
        """This method must be called to receive move completed messages"""
        self._send_message(MsgHwReqInfo())
        msg = self._wait_for_message(ID_MSG_HW_GET_INFO)
        data = struct.unpack("=l8sH4B48s12sHHH", msg.data)

        serial_no = data[0]
        model_no = data[1].rstrip(b'\x00').decode()
        type_ = data[2]
        fw_version = '.'.join(map(str, data[3:6]))
        notes = ', '.join(bs.rstrip(b'\x00').decode() for bs in data[7:9])
        hw_version, modstate, nchs = data[9:]

        return (serial_no, model_no, type_, fw_version, notes, hw_version,
            modstate, nchs)


class DDR25(_KBD101):
    steps_per_degree = 4000
    vel_scale = 26843.5
    acc_scale = 2.74878
    max_vel = 48318300
    max_acc = 28799
    homing_vel = int(48318300/10)
    offset = 0


class DDR05(_KBD101):
    steps_per_degree = 5555.55
    vel_scale = 37282.2
    acc_scale = 3.81775
    max_vel = int(1800*37282.2)
    max_acc = int(10477*3.81775)
    homing_vel = int(180*37282.5)
    offset = 0