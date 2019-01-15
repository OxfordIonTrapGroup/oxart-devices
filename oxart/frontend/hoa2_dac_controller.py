#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.hoa2_dac.driver import HOA2Dac
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import simple_network_args, init_logger
from oxart.tools import add_common_args


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", default=None,
                        help="serial device. See documentation for how to "
                             "specify a USB Serial Number.")

    simple_network_args(parser, 2030)
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if args.device is None:
        print("You need to specify -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)


    dev = HOA2Dac(serial_name=args.device)

    simple_server_loop({"hoa2_dac": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
