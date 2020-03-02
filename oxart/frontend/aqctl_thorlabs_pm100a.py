import argparse
import logging

import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop

from oxart.devices.thorlabs_pm.driver import ThorlabsPM100A


logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for Thorlabs PM100A power meter")

    # A list of available Thorlabs power meter devices can be obtained via
    # the get_device_names function in module oxart.devices.thorlabs_pm.driver
    parser.add_argument("-d", "--device",
                        default="USB0::0x1313::0x8079::P1003876::INSTR",
                        help="Hardware address of device")
    sca.simple_network_args(parser, 4315)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    logger.debug("Trying to establish connection to Thorlabs PM100A "
                 "power meter at {}...".format(args.device))

    dev = ThorlabsPM100A(args.device, False, False)
    logger.debug("Connection established.")

    try:
        logger.info("Starting server at port {}...".format(args.port))
        simple_server_loop({"Thorlabs PM100A": dev},
                           sca.bind_address_from_args(args), args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
