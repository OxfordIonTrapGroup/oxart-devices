#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.v3500a.driver import V3500A
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "Keysight V3500A RF power meter")
    parser.add_argument("-d", "--device", help="device's address")
    simple_network_args(parser, 4300)
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = V3500A(args.device)

    try:
        simple_server_loop({"V3500A": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
