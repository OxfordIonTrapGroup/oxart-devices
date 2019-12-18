#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.thorlabs_apt.driver import DDR05
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (simple_network_args, init_logger_from_args,
                         bind_address_from_args)
from oxart.tools import add_common_args

def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the "
                                    "Thorlabs DDR05 motorised rotation mount")
    simple_network_args(parser, 4001)
    parser.add_argument("-d", "--device", default=None,
                        help="serial device. See documentation for how to "
                             "specify a USB Serial Number.")
    parser.add_argument("--no-auto-home", action="store_true",
                        help="Do not home (reset to mechanical zero) on \
                        start (this needs to be done each time the hardware \
                        is power cycled")
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = DDR05(args.device, auto_home = not args.no_auto_home)

    simple_server_loop({"ddr05": dev}, bind_address_from_args(args), args.port)


if __name__ == "__main__":
    main()
