import driver
import time
import argparse
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger, bind_address_from_args

class PicoMirror:
    """ Picomotor controlled mirror """
    def __init__(self, device_ip, ch_horizontal, ch_vertical):
        self.device = driver.PicomotorController(device_ip)
        self.H = driver.PicoAxis(self.device, ch_horizontal)
        self.V = driver.PicoAxis(self.device, ch_vertical)
        print("Picomotor-controlled mirror initialised.")

    def move_absolute(self, pos_h, pos_v):
        self.H.move_absolute(pos_h)
        self.V.move_absolute(pos_v)

    def move_relative(self, delta_h, delta_v):
        self.H.move_relative(delta_h)
        self.V.move_relative(delta_v)

    def set_velocities(self, vel_h, vel_v):
        self.H.set_velocity(vel_h)
        self.V.set_velocity(vel_v)

    def get_velocities(self):
        return (self.H.get_velocity(), self.V.get_velocity())

    def get_position(self):
        return (self.H.get_position(), self.V.get_position())

    def move_indefinitely(self, dir_h, dir_v):
        self.H.move_indefinitely(dir_h)
        self.V.move_indefinitely(dir_v)

    def stop_motion(self):
        self.H.stop_motion()
        self.V.stop_motion()

    def set_home(self, home_h = 0, home_v = 0):
        self.H.set_home(home_h)
        self.V.set_home(home_v)

    def get_home(self):
        return (self.H.get_home(), self.V.get_home())

    def ping(self):
        return True

    def close(self):
        return

def main():
    parser = argparse.ArgumentParser()
    simple_network_args(parser, 3999)
    parser.add_argument("controller_ip", help = "IP address of Picomotor Controller")
    parser.add_argument("channel_h", type = int, help = "Channel of horizontal motor on controller")
    parser.add_argument("channel_v", type = int, help = "Channel of vertical motor on controller")
    verbosity_args(parser)
    args = parser.parse_args()
    init_logger(args)

    mirror = PicoMirror(args.controller_ip, args.channel_h, args.channel_v)
    try:
        simple_server_loop({'PicoMirror':mirror},
            bind_address_from_args(args), args.port)
    finally:
        mirror.close()

if __name__ == "__main__":
    main()
