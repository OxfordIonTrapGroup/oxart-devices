#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.thermostat.driver import Thermostat
from sipyco.pc_rpc import simple_server_loop
from oxart.tools import add_common_args
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "sinara Thermostat")
    parser.add_argument("-d", "--device", help="device's IP address")
    sca.simple_network_args(parser, 4300)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = Thermostat(args.device)

    # Q: Why not use try/finally for port closure?
    # A: We don't want to try to close the serial if sys.exit() is called,
    #    and sys.exit() isn't caught by Exception
    try:
        simple_server_loop({"Thermostat": dev}, 
                            sca.bind_address_from_args(args), args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
