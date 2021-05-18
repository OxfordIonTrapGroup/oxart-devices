import time
from driver import *


def print_status(h):
    h._send_message(MsgMotReqDcStatus())
    msg = h._wait_for_message(ID_MSG_DCSTATUSUPDATE)
    chan, position, velocity, _, status = struct.unpack("=HIHHI", msg.data)
    print(chan, position, velocity, status)
    status_str = ""
    if status & 0x80000000:
        status_str += "ENABLED, "
    if status & 0x200:
        status_str += "MOVE_HOME, "
    if status & 0x400:
        status_str += "HOMED, "
    if status & 0x10:
        status_str += "MOVE_FORWARD, "
    if status & 0x20:
        status_str += "MOVE_BACK, "
    print(status_str)


if __name__ == "__main__":
    h = DDR25("/dev/ttyUSB10", auto_home=False)

    # velocity = int(stage.vel_scale*DDR05.max_vel - 1)
    # acceleration = int(stage.acc_scale*stage.max_acc - 1)
    # h.set_home_params(velocity=int(stage.vel_scale*180))
    # h.set_velocity_params(vel_max=velocity, acc=acceleration)
    # h._send_message(MsgMotAckDcStatusUpdate())
    # h._send_message(MsgMotResumeEndOfMoveMsgs())

    h.home()
    print_status(h)

    # for _ in range(5):
    #    print_status(h)
    #    time.sleep(0.2)

    print("Moving ...")
    for i in range(1, 37):
        h.set_angle(i * 10)
        time.sleep(0.2)
