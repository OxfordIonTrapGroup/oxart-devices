from artiq.language.core import *
import numpy as np
import time

class ShutterWrapper:
    """
    Wraps one or more shutter drivers to allow reference to channels by an
    easily remappable logical name. The arguments are:
        'devices', the list of shutter controllers, and
        'mappings', a dictionary mapping logical devices names to
            (device,channel) tuples
    """
    def __init__(self, dmgr, devices, mappings):
        self.core = dmgr.get("core")
        self.devices = { dev: dmgr.get(dev) for dev in devices }
        
        self.mappings = mappings

    def _get_dev_channel(self, channel):
        """Return a (device handle, channel) tuple given a logical channel"""
        try:
            (device_name,ch) = self.mappings[channel]
        except KeyError:
            raise UnknownLogicalChannel

        try:
            device = self.devices[device_name]
        except KeyError:
            raise UnknownDeviceName

        return (device, ch)

    def set_shutter(self, channel, value):
        """Set a shutter state"""
        (device, ch) = self._get_dev_channel(channel)
        device.set_shutter(ch, value)

    def get_shutter(self, channel):
        (device, ch) = self._get_dev_channel(channel)
        return device.get_shutter(ch)

    def open_shutter(self, channel):
        (device, ch) = self._get_dev_channel(channel)
        device.set_shutter(ch, True)

    def close_shutter(self, channel):
        # Look up device and channel
        (device, ch) = self._get_dev_channel(channel)
        device.set_shutter(ch, False)


class UnknownLogicalChannel(Exception):
    """The logical channel given was not found in the mappings dictionary"""
    pass

class UnknownDeviceName(Exception):
    """The device name for the given logical channel was not found in the devices list"""
    pass

