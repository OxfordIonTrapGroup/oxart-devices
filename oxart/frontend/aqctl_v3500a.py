#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.v3500a.driver import V3500A
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for " "Keysight V3500A RF power meter"
    )
    parser.add_argument("-d", "--device", help="device's address")
    sca.simple_network_args(parser, 4300)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = V3500A(args.device)

    try:
        simple_server_loop({"V3500A": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
