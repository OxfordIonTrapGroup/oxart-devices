#!/usr/bin/env python3.5

import argparse
import sys

from artiq_drivers.devices.conex_motor.driver import Conex
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args
from artiq.tools import init_logger, bind_address_from_args


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "Newport CONEX motorised micrometer")
    simple_network_args(parser, 4000)
    parser.add_argument("-d", "--device", default=None,
                        help="serial device. See documentation for how to "
                             "specify a USB Serial Number.")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    if args.device is None:
        print("You need to specify a -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)

    dev = Conex(args.device)

    # Q: Why not use try/finally for port closure?
    # A: We don't want to try to close the serial if sys.exit() is called,
    #    and sys.exit() isn't caught by Exception
    try:
        simple_server_loop({"conex": dev}, bind_address_from_args(args),
                           args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
