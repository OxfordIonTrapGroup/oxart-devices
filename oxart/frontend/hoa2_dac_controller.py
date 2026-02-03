#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.hoa2_dac.driver import HOA2Dac
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--device",
        default=None,
        help="serial device. See documentation for how to "
        "specify a USB Serial Number.",
    )

    sca.simple_network_args(parser, 2030)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    if args.device is None:
        print(
            "You need to specify -d/--device "
            "argument. Use --help for more information."
        )
        sys.exit(1)

    dev = HOA2Dac(serial_name=args.device)

    simple_server_loop({"hoa2_dac": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
