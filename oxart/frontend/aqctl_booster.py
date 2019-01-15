#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.booster.driver import Booster
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import simple_network_args, init_logger
from oxart.tools import add_common_args

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for Booster"
                                     " 8-channel RF power amplifier")
    parser.add_argument("-d", "--device", help="device's IP address")
    simple_network_args(parser, 4300)
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = Booster(args.device)

    try:
        simple_server_loop({"Booster": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
