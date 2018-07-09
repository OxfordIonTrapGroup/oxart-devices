#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.streams import Ethernet
from oxart.devices.prologix_gpib.driver import GPIB
from oxart.devices.lakeshore_335.driver import LakeShore335
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for Lake "
                                     "Shore Cryogenics model 335 temperature"
                                     "controllers")
    parser.add_argument("-d", "--device", help="GPIB controller IP address")
    parser.add_argument("-gpib", help="device's GPIB address", default=5)
    simple_network_args(parser, 4300)
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = LakeShore335(GPIB(Ethernet(args.device, 1234), args.gpib))

    try:
        simple_server_loop({"LakeShore335": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
