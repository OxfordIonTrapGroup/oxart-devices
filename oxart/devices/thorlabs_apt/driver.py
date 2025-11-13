import serial
import struct
import time
import logging
from enum import IntEnum

logger = logging.getLogger(__name__)

# See https://www.thorlabs.com/Software/Motion%20Control/APT_Communications_Protocol.pdf


class MGMSG(IntEnum):
    HW_DISCONNECT = 0x0002
    HW_REQ_INFO = 0x0005
    HW_GET_INFO = 0x0006
    HW_START_UPDATEMSGS = 0x0011
    HW_STOP_UPDATEMSGS = 0x0012
    HW_RESPONSE = 0x0080
    HW_RICHRESPONSE = 0x0081
    RACK_REQ_BAYUSED = 0x0060
    RACK_GET_BAYUSED = 0x0061
    RACK_REQ_STATUSBITS = 0x0226
    RACK_GET_STATUSBITS = 0x0227
    RACK_SET_DIGOUTPUTS = 0x0228
    RACK_REQ_DIGOUTPUTS = 0x0229
    RACK_GET_DIGOUTPUTS = 0x0230
    HUB_REQ_BAYUSED = 0x0065
    HUB_GET_BAYUSED = 0x0066
    MOD_SET_CHANENABLESTATE = 0x0210
    MOD_REQ_CHANENABLESTATE = 0x0211
    MOD_GET_CHANENABLESTATE = 0x0212
    MOD_SET_DIGOUTPUTS = 0x0213
    MOD_REQ_DIGOUTPUTS = 0x0214
    MOD_GET_DIGOUTPUTS = 0x0215
    MOD_IDENTIFY = 0x0223
    MOT_SET_ENCCOUNTER = 0x0409
    MOT_REQ_ENCCOUNTER = 0x040A
    MOT_GET_ENCCOUNTER = 0x040B
    MOT_SET_POSCOUNTER = 0x0410
    MOT_REQ_POSCOUNTER = 0x0411
    MOT_GET_POSCOUNTER = 0x0412
    MOT_SET_VELPARAMS = 0x0413
    MOT_REQ_VELPARAMS = 0x0414
    MOT_GET_VELPARAMS = 0x0415
    MOT_SET_JOGPARAMS = 0x0416
    MOT_REQ_JOGPARAMS = 0x0417
    MOT_GET_JOGPARAMS = 0x0418
    MOT_SET_LIMSWITCHPARAMS = 0x0423
    MOT_REQ_LIMSWITCHPARAMS = 0x0424
    MOT_GET_LIMSWITCHPARAMS = 0x0425
    MOT_SET_POWER_PARAMS = 0x0426
    MOT_REQ_POWER_PARAMS = 0x0427
    MOT_GET_POWER_PARAMS = 0x0428
    MOT_REQ_STATUSBITS = 0x0429
    MOT_GET_STATUSBITS = 0x042A
    MOT_SET_GENMOVEPARAMS = 0x043A
    MOT_REQ_GENMOVEPARAMS = 0x043B
    MOT_GET_GENMOVEPARAMS = 0x043C
    MOT_SET_HOMEPARAMS = 0x0440
    MOT_REQ_HOMEPARAMS = 0x0441
    MOT_GET_HOMEPARAMS = 0x0442
    MOT_MOVE_HOME = 0x0443
    MOT_MOVE_HOMED = 0x0444
    MOT_SET_MOVERELPARAMS = 0x0445
    MOT_REQ_MOVERELPARAMS = 0x0446
    MOT_GET_MOVERELPARAMS = 0x0447
    MOT_MOVE_RELATIVE = 0x0448
    MOT_SET_MOVEABSPARAMS = 0x0450
    MOT_REQ_MOVEABSPARAMS = 0x0451
    MOT_GET_MOVEABSPARAMS = 0x0452
    MOT_MOVE_ABSOLUTE = 0x0453
    MOT_MOVE_VELOCITY = 0x0457
    MOT_MOVE_COMPLETED = 0x0464
    MOT_MOVE_STOP = 0x0465
    MOT_MOVE_STOPPED = 0x0466
    MOT_MOVE_JOG = 0x046A
    MOT_SUSPEND_ENDOFMOVEMSGS = 0x046B
    MOT_RESUME_ENDOFMOVEMSGS = 0x046C
    MOT_REQ_DCSTATUSUPDATE = 0x0490
    MOT_GET_DCSTATUSUPDATE = 0x0491
    MOT_ACK_DCSTATUSUPDATE = 0x0492
    MOT_SET_DCPIDPARAMS = 0x04A0
    MOT_REQ_DCPIDPARAMS = 0x04A1
    MOT_GET_DCPIDPARAMS = 0x04A2
    MOT_SET_POTPARAMS = 0x04B0
    MOT_REQ_POTPARAMS = 0x04B1
    MOT_GET_POTPARAMS = 0x04B2
    MOT_SET_AVMODES = 0x04B3
    MOT_REQ_AVMODES = 0x04B4
    MOT_GET_AVMODES = 0x04B5
    MOT_SET_BUTTONPARAMS = 0x04B6
    MOT_REQ_BUTTONPARAMS = 0x04B7
    MOT_GET_BUTTONPARAMS = 0x04B8
    MOT_SET_EEPROMPARAMS = 0x04B9
    PZ_SET_POSCONTROLMODE = 0x0640
    PZ_REQ_POSCONTROLMODE = 0x0641
    PZ_GET_POSCONTROLMODE = 0x0642
    PZ_SET_OUTPUTVOLTS = 0x0643
    PZ_REQ_OUTPUTVOLTS = 0x0644
    PZ_GET_OUTPUTVOLTS = 0x0645
    PZ_SET_OUTPUTPOS = 0x0646
    PZ_REQ_OUTPUTPOS = 0x0647
    PZ_GET_OUTPUTPOS = 0x0648
    PZ_SET_INPUTVOLTSSRC = 0x0652
    PZ_REQ_INPUTVOLTSSRC = 0x0653
    PZ_GET_INPUTVOLTSSRC = 0x0654
    PZ_SET_PICONSTS = 0x0655
    PZ_REQ_PICONSTS = 0x0656
    PZ_GET_PICONSTS = 0x0657
    PZ_REQ_PZSTATUSBITS = 0x065B
    PZ_GET_PZSTATUSBITS = 0x065C
    PZ_GET_PZSTATUSUPDATE = 0x0661
    PZ_ACK_PZSTATUSUPDATE = 0x0662
    PZ_SET_OUTPUTLUT = 0x0700
    PZ_REQ_OUTPUTLUT = 0x0701
    PZ_GET_OUTPUTLUT = 0x0702
    PZ_SET_OUTPUTLUTPARAMS = 0x0703
    PZ_REQ_OUTPUTLUTPARAMS = 0x0704
    PZ_GET_OUTPUTLUTPARAMS = 0x0705
    PZ_START_LUTOUTPUT = 0x0706
    PZ_STOP_LUTOUTPUT = 0x0707
    PZ_SET_ZERO = 0x0658
    PZ_SET_OUTPUTMAXVOLTS = 0x0680
    PZ_REQ_OUTPUTMAXVOLTS = 0x0681
    PZ_GET_OUTPUTMAXVOLTS = 0x0682
    PZ_SET_SLEWRATES = 0x0683
    PZ_REQ_SLEWRATES = 0x0684
    PZ_GET_SLEWRATES = 0x0685
    RESTOREFACTORYSETTINGS = 0x0686


class SRC_DEST(IntEnum):
    HOST_CONTROLLER = 0x01
    RACK_CONTROLLER = 0x11
    RACK_BAY_0 = 0x21
    RACK_BAY_1 = 0x22
    RACK_BAY_2 = 0x23
    RACK_BAY_3 = 0x24
    RACK_BAY_4 = 0x25
    RACK_BAY_5 = 0x26
    RACK_BAY_6 = 0x27
    RACK_BAY_7 = 0x28
    RACK_BAY_8 = 0x29
    RACK_BAY_9 = 0x2A
    GENERIC_USB_HW = 0x50


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
    MOVING = (MOVING_HOME | MOVING_FORWARD | MOVING_REVERSE
              | JOGGING_FORWARD | JOGGING_REVERSE)


class Direction(IntEnum):
    FORWARD = 1
    REVERSE = 2


class LimitSwitch(IntEnum):
    REVERSE = 1
    FORWARD = 4


class MsgError(Exception):
    pass


class Message:

    def __init__(self,
                 _id,
                 param1=0,
                 param2=0,
                 dest=SRC_DEST.GENERIC_USB_HW.value,
                 src=SRC_DEST.HOST_CONTROLLER.value,
                 data=None):
        if data is not None:
            dest |= 0x80
        self._id = _id
        self.param1 = param1
        self.param2 = param2
        self.dest = dest
        self.src = src
        self.data = data

    def __str__(self):
        return ("<Message 0x{:04x} p1=0x{:02x} p2=0x{:02x} "
                "dest=0x{:02x} src=0x{:02x}>".format(self._id, self.param1, self.param2,
                                                     self.dest, self.src))

    @staticmethod
    def unpack(data):
        _id, param1, param2, dest, src = struct.unpack("<HBBBB", data[:6])
        data = data[6:]
        if dest & 0x80:
            if data and len(data) != param1 | (param2 << 8):
                raise ValueError("If data are provided, param1 and param2"
                                 " should contain the data length")
        else:
            data = None
        return Message(MGMSG(_id), param1, param2, dest, src, data)

    def pack(self):
        if self.has_data:
            return struct.pack("<HHBB", self._id.value, len(self.data),
                               self.dest | 0x80, self.src) + self.data
        else:
            return struct.pack("<HBBBB", self._id.value, self.param1, self.param2,
                               self.dest, self.src)

    @property
    def has_data(self):
        return self.dest & 0x80

    @property
    def data_size(self):
        if self.has_data:
            return self.param1 | (self.param2 << 8)
        else:
            raise ValueError


class _APTDevice:

    def __init__(self, port):
        self.h = serial.Serial(port, 115200, write_timeout=0.1)
        self._status_update_counter = 0

    def _send_message(self, message):
        msg = message.pack()
        logger.debug("Sending: {}".format(message))
        logger.debug("tx: {}".format(msg.hex()))
        self.h.write(msg)

    def _read_message(self):
        header = self.h.read(6)
        data = b""
        if header[4] & 0x80:
            (length, ) = struct.unpack("<H", header[2:4])
            data = self.h.read(length)
        msg = Message.unpack(header + data)
        logger.debug("rx: {}{}".format(header.hex(), data.hex()))
        logger.debug("Received: {}".format(msg))
        return msg

    def _send_request(self, msgreq_id, wait_for, param1=0, param2=0, data=None):
        self._send_message(Message(msgreq_id, param1, param2, data=data))
        while True:
            msg = self._read_message()
            self._triage_message(msg)

            if msg._id in wait_for:
                return msg

    def _triage_message(self, msg):
        """Triage an incoming message in case of errors or action required."""
        msg_id = msg._id
        data = msg.data

        if msg_id == MGMSG.HW_DISCONNECT:
            raise MsgError("Error: Please disconnect")
        elif msg_id == MGMSG.HW_RESPONSE:
            raise MsgError("Hardware error, please disconnect")
        elif msg_id == MGMSG.HW_RICHRESPONSE:
            (code, ) = struct.unpack("<H", data[2:4])
            raise MsgError("Hardware error {}: {}".format(
                code, data[4:].decode(encoding="ascii")))
        elif msg_id in [
                MGMSG.MOT_MOVE_COMPLETED, MGMSG.MOT_MOVE_STOPPED, MGMSG.MOT_MOVE_HOMED,
                MGMSG.MOT_GET_DCSTATUSUPDATE
        ]:
            self._status_update_counter += 1
            if self._status_update_counter > 25:
                logger.debug("Acking status updates")
                self._status_update_counter = 0
                self.ack_status_update()

    def identify(self):
        self._send_message(Message(MGMSG.MOD_IDENTIFY))

    def set_channel_enable(self, enable=True, channel=0):
        active = 1 if enable else 2
        self._send_message(
            Message(MGMSG.MOD_SET_CHANENABLESTATE, param1=channel, param2=active))

    def set_home_params(self, velocity=0, offset=0, channel=0):
        direction = Direction.REVERSE
        limit = LimitSwitch.REVERSE
        payload = struct.pack("<HHHii", channel, direction, limit, velocity, offset)
        self._send_message(Message(MGMSG.MOT_SET_HOMEPARAMS, data=payload))

    def set_velocity_params(self, vel_min=0, vel_max=0, acc=0, channel=0):
        payload = struct.pack("<Hiii", channel, vel_min, acc, vel_max)
        self._send_message(Message(MGMSG.MOT_SET_VELPARAMS, data=payload))

    def get_status(self):
        msg = self._send_request(MGMSG.MOT_REQ_DCSTATUSUPDATE,
                                 wait_for=[MGMSG.MOT_GET_DCSTATUSUPDATE])
        chan, position, velocity, _, status = struct.unpack("=HiHHI", msg.data)
        return chan, position, velocity, status

    def get_status_bits(self):
        msg = self._send_request(MGMSG.MOT_REQ_STATUSBITS,
                                 wait_for=[MGMSG.MOT_GET_STATUSBITS])
        _, status = struct.unpack("=HI", msg.data)
        return status

    def suspend_end_of_move_messages(self):
        self._send_message(Message(MGMSG.MOT_SUSPEND_ENDOFMOVEMSGS))

    def resume_end_of_move_messages(self):
        self._send_message(Message(MGMSG.MOT_RESUME_ENDOFMOVEMSGS))

    def ack_status_update(self):
        self._send_message(Message(MGMSG.MOT_ACK_DCSTATUSUPDATE))

    def home(self, channel=0):
        logger.debug("Homing...")
        self._send_request(MGMSG.MOT_MOVE_HOME,
                           param1=channel,
                           wait_for=[MGMSG.MOT_MOVE_HOMED, MGMSG.MOT_MOVE_STOPPED])
        logger.debug("Homed")

    def move(self, position, channel=0):
        payload = struct.pack("<Hi", channel, position)
        self._send_request(MGMSG.MOT_MOVE_ABSOLUTE,
                           data=payload,
                           wait_for=[MGMSG.MOT_MOVE_COMPLETED])

    def move_relative(self, position_change, channel=0):
        payload = struct.pack("<Hi", channel, position_change)
        self._send_request(MGMSG.MOT_MOVE_RELATIVE,
                           data=payload,
                           wait_for=[MGMSG.MOT_MOVE_COMPLETED])

    def stop(self):
        self._send_request(MGMSG.MOT_MOVE_STOP, wait_for=[MGMSG.MOT_MOVE_STOPPED])

    def get_position(self):
        _, position, *_ = self.get_status()
        return position

    def is_moving(self):
        status = self.get_status_bits()
        return (status & Status.MOVING) != 0

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

    def close(self):
        self.h.close()

    def ping(self):
        try:
            self.get_status()
        except Exception:
            return False
        return True


class _APTRotation(_APTDevice):
    """Generic class of rotation mounts."""

    def __init__(self, port, auto_home=True):
        super().__init__(port)

        self.setup()
        if auto_home:
            self.home()

    def setup(self):
        self.set_channel_enable(True)
        self.set_velocity_params(acc=self.max_acc, vel_max=self.max_vel)
        self.set_home_params(velocity=self.homing_vel, offset=self.offset)

    def home(self):
        super().home()
        self._last_angle_mu = None

    def set_angle(self, angle, check_position=False, auto_retry=0, acceptable_error=0):
        """Set angle in degrees.

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
                self.check_angle_mu(acceptable_error=acceptable_error)
            except ValueError:
                if auto_retry > 0:
                    self.set_angle(angle,
                                   check_position=check_position,
                                   auto_retry=auto_retry - 1,
                                   acceptable_error=acceptable_error)
                else:
                    raise

    def get_angle(self):
        """Get current angle in degrees."""
        angle_mu = self.get_position()
        angle = float(angle_mu) / self.steps_per_degree
        angle = angle % 360
        return angle

    def check_angle_mu(self, acceptable_error=0):
        """Check currently set angle against stored value."""
        if self._last_angle_mu is None:
            # nothing to check against
            return

        angle_mu = self.get_position()
        if abs(self._last_angle_mu - angle_mu) > acceptable_error:
            raise ValueError("Last angle set does not match current angle",
                             self._last_angle_mu, angle_mu)
        else:
            # if we're off by an acceptable amount, store the actual value
            self._last_angle_mu = angle_mu


class K10CR1(_APTRotation):
    steps_per_degree = 136533
    max_acc = 15020
    max_vel = 73300775
    homing_vel = 7300775
    offset = 546133

    def setup(self):
        super().setup()
        self.set_power_params(0.05, 0.3)

    def set_power_params(self, hold_power=0, move_power=0):
        assert hold_power >= 0 and hold_power <= 1
        assert move_power >= 0 and move_power <= 1
        hold_factor = int(hold_power * 100)
        move_factor = int(move_power * 100)
        channel = 0
        payload = struct.pack("<HHH", channel, hold_factor, move_factor)
        self._send_message(Message(MGMSG.MOT_SET_POWER_PARAMS, data=payload))

    def set_angle(self, angle):
        """Set angle in degrees."""
        # These drivers are slow, so need to intelligently choose rotation
        # direction if we can to minimize rotation distance.
        angle = angle % 360
        angle_mu = int(angle * self.steps_per_degree)

        if self._last_angle_mu:
            # We know our last position, so we can do a relative move
            delta = angle_mu - self._last_angle_mu
            for offset in [360 * self.steps_per_degree, -360 * self.steps_per_degree]:
                if abs(delta + offset) < abs(delta):
                    delta += offset
            self.move_relative(delta)
        else:
            self.move(angle_mu)
        self._last_angle_mu = angle_mu


class _KBD101(_APTRotation):
    """This will not work if instantiated directly."""

    def setup(self):
        super().setup()
        self.req_hw_info()

    def req_hw_info(self):
        """This method must be called to receive move completed messages."""
        msg = self._send_request(MGMSG.HW_REQ_INFO, wait_for=[MGMSG.HW_GET_INFO])
        data = struct.unpack("=l8sH4B48s12sHHH", msg.data)

        serial_no = data[0]
        model_no = data[1].rstrip(b'\x00').decode()
        type_ = data[2]
        fw_version = '.'.join(map(str, data[3:6]))
        notes = ', '.join(bs.rstrip(b'\x00').decode() for bs in data[7:9])
        hw_version, modstate, nchs = data[9:]

        return (serial_no, model_no, type_, fw_version, notes, hw_version, modstate,
                nchs)


class DDR25(_KBD101):
    steps_per_degree = 4000
    vel_scale = 26843.5
    acc_scale = 2.74878
    max_vel = 48318300
    max_acc = 28799
    homing_vel = int(48318300 / 10)
    offset = 0


class DDR05(_KBD101):
    steps_per_degree = 5555.55
    vel_scale = 37282.2
    acc_scale = 3.81775
    max_vel = int(1800 * 37282.2)
    max_acc = int(10477 * 3.81775)
    homing_vel = int(180 * 37282.5)
    offset = 0
