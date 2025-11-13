class ShutterWrapper:
    """Wraps one or more shutter drivers to allow reference to channels by an easily
    remappable logical name.

    The arguments are:
    'mappings': a dictionary mapping logical devices names to
        (device,channel) tuples
    """

    def __init__(self, dmgr, mappings):
        for channel in mappings:
            dev_name, ch = mappings[channel]
            dev = dmgr.get(dev_name)
            channel_cls = ShutterChannel(dev, ch)
            setattr(self, channel, channel_cls)


class ShutterChannel:

    def __init__(self, dev, channel):
        self.dev = dev
        self.channel = channel

    def set(self, state):
        self.dev.set_state(self.channel, state)

    def on(self):
        self.set(True)

    def off(self):
        self.set(False)
