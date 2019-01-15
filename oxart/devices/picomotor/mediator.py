from artiq.language.core import *

class PicoMirror:
    """
    Wraps multiple picomotor controllers and channels to allow addressing a
    mirror by instance. The arguments are:
        'motor_horizontal',
        'motor_vertical',
    each of which is a pair of (device, channel number) the respective motor
    is attached to.
    """
    def __init__(self, dmgr, motor_horizontal, motor_vertical):
        self.devs = (dmgr.get(motor_horizontal[0]),
                                            dmgr.get(motor_vertical[0]))
        self.chnls = (motor_horizontal[1], motor_vertical[1])

    def move_absolute(self, pos):
        # pos is a (x,y) pair
        for i in [0, 1]:
            self.devs[i].move_absolute(self.chnls[i], pos[i])

    def move_relative(self, delta):
        # delta is a (x,y) pair
        for i in [0, 1]:
            self.devs[i].move_relative(self.chnls[i], delta[i])

    def set_velocities(self, vel):
        # vel is a (x,y) pair
        for i in [0, 1]:
            self.devs[i].set_velocity(self.chnls[i], vel[i])

    def get_velocities(self):
        return (self.devs[0].get_velocity(self.chnls[0]),
                self.devs[1].get_velocity(self.chnls[1]))

    def get_position(self):
        return (self.devs[0].get_position(self.chnls[0]),
                self.devs[1].get_position(self.chnls[1]))

    def move_indefinitely(self, axis, direction):
        # axis is either 0 (horizontal) or 1 (vertical)
        # dir is '+' or '-'
        self.devs[axis].move_indefinitely(self.chnls[axis], direction)

    def stop_motion(self):
        for i in [0, 1]:
            self.devs[i].stop_motion(self.chnls[i])

    def set_home(self, home = (0,0)):
        for i in [0, 1]:
            self.devs[i].set_home(self.chnls[i], home)

    def get_home(self):
        return (self.devs[0].get_home(self.chnls[0]),
                self.devs[1].get_home(self.chnls[1]))

    def ping(self):
        return True

    def close(self):
        return
