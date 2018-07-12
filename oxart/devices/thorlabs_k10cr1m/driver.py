import logging
import serial
import re
import sys
import asyncio
import thorlabs_apt as apt

import artiq.protocols.pyon as pyon

logger = logging.getLogger(__name__)
class K10CR1MDriver:
    def __init__(self, serial=None):
        dev_list = apt.list_available_devices()

        if len(dev_list) == 0:
            raise Exception("No APT devices found")


        if [dev[0] is 50 for dev in dev_list]:
            dev_sn_available = [dev[1] for dev in dev_list]

        if len(dev_sn_available) == 0:
            raise Exception("No K10CR1 devices found")


        if serial is None:
            serial = dev_sn_available[0]

        # Check serial number is present in available devices

        try:
            dev_sn_available.index(serial)
        except ValueError:
            raise ValueError("No device with serial number {} present (available = {})"\
                .format(serial, dev_sn_available))

        self.dev = apt.Motor(serial)

        #home the motor - a bug in the software is that home parameters must be set
        #have set them to the 0 position on the vernier
        self.dev.set_move_home_parameters(2,1,1,4)
        self.dev.move_home(True)

        self.dev.set_velocity_parameter(0,4,6)

        def set_angle(self, angle):
            self.dev.move_to(angle, blocking=True)

        def get_angle(self):
            return self.dev.position

        def ping(self):
            return True