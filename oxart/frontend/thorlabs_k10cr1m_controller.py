#!/usr/bin/env python3.5

import argparse
import sys

from artiqDrivers.devices.thorlabs_k10cr1m.driver import K10CR1MDriver
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger

def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the Thorlabs K10CR1/M motorised rotation mount")
    simple_network_args(parser, 4010)
    parser.add_argument("-s", "--serial", default=None,
                        help="serial number of device. Uses first device if not provided")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = K10CR1MDriver(serial=args.serial)

    simple_server_loop({"k10cr1/m": dev}, args.bind, args.port)

if __name__ == "__main__":
    main()
