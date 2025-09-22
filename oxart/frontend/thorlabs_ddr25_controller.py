#!/usr/bin/env python3.5

import argparse

from oxart.devices.thorlabs_apt.driver import DDR25
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the "
                                     "Thorlabs DDR25 motorised rotation mount")
    sca.simple_network_args(parser, 4000)
    parser.add_argument(
        "-d",
        "--device",
        default=None,
        help="serial device. See documentation for how to "
        "specify a USB Serial Number.",
    )
    parser.add_argument(
        "--no-auto-home",
        action="store_true",
        help="Do not home (reset to mechanical zero) on \
                        start (this needs to be done each time the hardware \
                        is power cycled",
    )
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = DDR25(args.device, auto_home=not args.no_auto_home)

    simple_server_loop({"ddr25": dev}, sca.bind_address_from_args(args), args.port)


if __name__ == "__main__":
    main()
