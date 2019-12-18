#!/usr/bin/env python3.5

import argparse
import sys

from artiq_drivers.devices.arduino_dds.driver import ArduinoDDS, ArduinoDDSSim
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--device", default=None,
                        help="serial device. See documentation for how to "
                             "specify a USB Serial Number.")
    parser.add_argument("--simulation", action="store_true",
                        help="Put the driver in simulation mode, even if "
                             "--device is used.")
    parser.add_argument("--clockfreq", default=1e9, type=float,
                        help="clock frequency provided to DDS")

    simple_network_args(parser, 2000)
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    if not args.simulation and args.device is None:
        print("You need to specify either --simulation or -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)

    if args.simulation:
        dev = ArduinoDDSSim()
    else:
        dev = ArduinoDDS(addr=args.device, clock_freq=args.clockfreq)

    simple_server_loop({"arduino_dds": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
