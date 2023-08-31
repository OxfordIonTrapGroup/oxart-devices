#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.scpi_dmm.driver import ScpiDmm
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "SCPI Digital Multi Meters")
    parser.add_argument("-d", "--device", help="device's hardware address")

    sca.simple_network_args(parser, 4300)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = ScpiDmm(args.device)

    try:
        simple_server_loop({"ScpiDmm": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
