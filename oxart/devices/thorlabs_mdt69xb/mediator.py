import numpy as np
import time


class PiezoWrapper:
    """Wraps multiple piezo controllers to allow reference to channels by an easily
    remappable logical name.

    The arguments are:
    'devices', the list of piezo controllers,
    'mappings', a dictionary mapping logical devices names to
        (device,channel) tuples, and
    'slow_scan', a dictionary mapping the logical devices which require
        incremented voltage steps to the maximum step size in volts.
    """

    def __init__(self, dmgr, devices, mappings, slow_scan):
        self.core = dmgr.get("core")
        self.devices = {dev: dmgr.get(dev) for dev in devices}

        self.mappings = mappings
        self.slow_scan = slow_scan

    def set_channel(self, logical_ch, value, force=False):
        """Set a channel to a value.

        'force' flag should only be used when calibrating a slow scan channel
        """
        # Look up device and channel
        (device, channel) = self._get_dev_channel(logical_ch)

        # Set the physical device & channel to the given value
        if logical_ch in self.slow_scan and not force:
            step = self.slow_scan[logical_ch]
            current = device.get_channel(channel)
            if current < 0:
                err_msg = ("'{}' has no setpoint. ".format(logical_ch) +
                           "Calibrate with laser unlocked before reuse.")
                raise NoSetpointError(err_msg)
            else:
                sgn = np.sign(value - current)
                while abs(value - current) > step:
                    current += sgn * step
                    device.set_channel(channel, current)
                    time.sleep(0.01)
        device.set_channel(channel, value)

    def get_channel_output(self, logical_ch):
        # Look up device and channel
        (device, channel) = self._get_dev_channel(logical_ch)

        # Get physical device & channel output value
        return device.get_channel_output(channel)

    def get_channel(self, logical_ch):
        # Look up device and channel
        (device, channel) = self._get_dev_channel(logical_ch)

        # Get physical device & channel value
        return device.get_channel(channel)

    def save_setpoints(self, logical_ch):
        """Deprecated, since we save setpoints every time we set, so we no longer
        need to call this function explicitly.

        Save setpoints for controller with given logical channel.
        """
        (dev, _) = self._get_dev_channel(logical_ch)
        dev.save_setpoints()

    def _get_dev_channel(self, logical_ch):
        """Return a (device handle, channel) tuple given a logical channel."""
        # Look up (device name, channel name) in mappings dictionary
        try:
            (device_name, channel) = self.mappings[logical_ch]
        except KeyError:
            raise UnknownLogicalChannel

        # Find the handle to the device class given by device name
        try:
            device = self.devices[device_name]
        except KeyError:
            raise UnknownDeviceName

        return (device, channel)


class UnknownLogicalChannel(Exception):
    """Logical channel given not found in mappings dictionary."""
    pass


class UnknownDeviceName(Exception):
    """Device name for given logical channel not found in devices list."""
    pass


class NoSetpointError(Exception):
    """No setpoint available for a slow scan piezo, needs calibration."""
    pass
