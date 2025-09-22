#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.hex_controller_C88752.driver import Hexapod
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "PI Hexapod Controller C-887.52")
    parser.add_argument("-d", "--device", help="Hexapod's IP address")

    sca.simple_network_args(parser, 4302)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = Hexapod(args.device)

    try:
        simple_server_loop({"Hexapod Controller": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
