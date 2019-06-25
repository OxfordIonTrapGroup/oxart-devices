#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.agilent_6671a.driver import Agilent6671A
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import simple_network_args, init_logger
from oxart.tools import add_common_args

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "Agilent 6671A power supplies")
    parser.add_argument("-d", "--device", help="device's hardware address")

    simple_network_args(parser, 4300)
    add_common_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = Agilent6671A(args.device)

    try:
        simple_server_loop({"psu": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
