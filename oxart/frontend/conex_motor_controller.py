#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.conex_motor.driver import Conex
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "Newport CONEX motorised micrometer")
    sca.simple_network_args(parser, 4000)
    parser.add_argument("-d",
                        "--device",
                        default=None,
                        help="serial device. Likely in the form of 'COM[X]' where '[X]' is some number"
                        " according to how it appears in the GUI about page or Windows Device Manager. "
                        "Otherwise see Conex documentation for how to "
                        "specify a USB Serial Number. ")
    parser.add_argument("--no-auto-home",
                        action="store_true",
                        help="Do not home (reset to mechanical zero) on \
                        start (this needs to be done each time the hardware is \
                        power cycled")
    parser.add_argument("--position-limit",
                        default=None,
                        type=float,
                        help="Maximum extension of micrometer (limit loaded \
                        into hardware")
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    if args.device is None:
        print("You need to specify a -d/--device "
              "argument. Use --help for more information.")
        sys.exit(1)

    dev = Conex(args.device,
                position_limit=args.position_limit,
                auto_home=not args.no_auto_home)

    # Q: Why not use try/finally for port closure?
    # A: We don't want to try to close the serial if sys.exit() is called,
    #    and sys.exit() isn't caught by Exception
    try:
        print('Running conex server')
        simple_server_loop({"conex_waveguide_objective": dev}, sca.bind_address_from_args(args), args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
