import logging
import thorlabs_apt as apt

K10CR1_TYPE = 50

logger = logging.getLogger(__name__)
class K10CR1MDriver:
    def __init__(self, sn=None):
        dev_list = apt.list_available_devices()

        if len(dev_list) == 0:
            raise Exception("No APT devices found")

        dev_sn_available = [dev[1] for dev in dev_list if dev[0] == K10CR1_TYPE]
        logger.info("Found serial nos. {}".format(dev_sn_available))

        if len(dev_sn_available) == 0:
            raise Exception("No K10CR1 devices found")

        if sn is None:
            sn = dev_sn_available[0]

        # Check serial number is present in available devices
        if sn not in dev_sn_available:
            raise ValueError("No device with serial no. {} present (available = {})"\
                .format(sn, dev_sn_available))

        logger.debug("Initialising connection to motor serial no. {}".format(sn))
        self.dev = apt.Motor(sn)

        #home the motor - a bug in the software is that home parameters must be set
        #have set them to the 0 position on the vernier
        logger.debug("Homing motor serial no. {}".format(sn))
        self.dev.set_move_home_parameters(2,1,1,4)
        self.dev.move_home(True)

        logger.debug("Setting velocity parameters for motor serial no. {}".format(sn))
        self.dev.set_velocity_parameters(0,4,6)

    def set_angle(self, angle):
        """Set angle in degrees"""
        self.dev.move_to(angle, blocking=True)

    def get_angle(self):
        """Get angle in degrees"""
        return self.dev.position

    def ping(self):
        return True
