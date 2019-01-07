import driver
import time

class PicoMirror:
    """ Picomotor controlled mirror """
    def __init__(self, device_ip, ch_horizontal, ch_vertical):
        self.device = driver.PicomotorController(device_ip)
        self.H = driver.PicoAxis(self.device, ch_horizontal)
        self.V = driver.PicoAxis(self.device, ch_vertical)

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
