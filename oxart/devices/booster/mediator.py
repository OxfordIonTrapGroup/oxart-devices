from oxart.devices.booster.driver import Booster
from oxart.devices.mediator import multi_channel_dev_mediator


@multi_channel_dev_mediator
class Boosters:
    """ Wraps multiple Boosters to allow reference to channels by an
    easily remappable logical name.

    Methods are dynamically created from the driver class (see the docstring
    for more info).
    """
    _driver_cls = Booster

    def __init__(self, dmgr, devices, mappings):
        """
        :param devices: list of amplifier names
        :param channels: dictionary mapping logical names to (device, channel)
          tuples
        """
        self.core = dmgr.get("core")
        self.devices = {dev: dmgr.get(dev) for dev in devices}
        self.mappings = mappings
