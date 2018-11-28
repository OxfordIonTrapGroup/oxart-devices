#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.scpi_dmm.driver import ScpiDmm
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "SCPI Digital Multi Meters")
    parser.add_argument("-d", "--device", help="device's hardware address")

    simple_network_args(parser, 4300)
    verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = ScpiDmm(args.device)

    try:
        simple_server_loop({"ScpiDmm": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
