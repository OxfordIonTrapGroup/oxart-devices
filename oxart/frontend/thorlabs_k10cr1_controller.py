#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.thorlabs_k10cr1.driver import K10CR1
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import (verbosity_args, simple_network_args, init_logger
                                                    bind_address_from_args)

def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the "
                                    "Thorlabs K10CR1 motorised rotation mount")
    simple_network_args(parser, 4000)
    parser.add_argument("-d", "--device", default=None,
                        help="serial device. See documentation for how to "
                             "specify a USB Serial Number.")
    parser.add_argument("--no-auto-home", action="store_true",
                        help="Do not home (reset to mechanical zero) on \
                        start (this needs to be done each time the hardware is \
                        power cycled")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = K10CR1(args.device, auto_home = not args.no_auto_home)

    # Q: Why not use try/finally for port closure?
    # A: We don't want to try to close the serial if sys.exit() is called,
    #    and sys.exit() isn't caught by Exception
    try:
        simple_server_loop({"k10cr1": dev}, bind_address_from_args(args),
                           args.port)
    except Exception:
        dev.close()
    else:
        dev.close()

if __name__ == "__main__":
    main()
