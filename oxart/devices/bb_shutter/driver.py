import logging
from Adafruit_BBIO import GPIO

logger = logging.getLogger(__name__)


class BBShutter:
    """Driver that runs on a BeagleBone and controls 4 shutters.

    All methods use the following notation:
    channel: channel index [0..3]
    state: True = open = not blocking beam. False = closed = blocking beam
    """
    def __init__(self):
        self.pins = ["P9_14", "P9_16", "P9_21", "P9_22"]
        self.states = [False] * len(self.pins)

        for pin in self.pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

    def set_shutter(self, channel, state):
        """Set a shutter state"""
        if channel > 3 or channel < 0:
            raise ValueError("Channel out of range")

        GPIO.output(self.pins[channel], GPIO.HIGH if state else GPIO.LOW)
        self.states[channel] = not (not (state))

    def get_shutter(self, channel):
        """Get a shutter state"""
        if channel > 3 or channel < 0:
            raise ValueError("Channel out of range")
        return self.states[channel]

    def open_shutter(self, channel):
        """Set a shutter to the open = not blocking beam state"""
        self.set_shutter(channel, True)

    def close_shutter(self, channel):
        """Set a shutter to the closed = blocking beam state"""
        self.set_shutter(channel, False)
