#!/usr/bin/env python3.5

import argparse

from oxart.devices.vaunix_signal_generator.driver import VaunixSG
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the "
                                     "Vaunix Lab brick signal generator")
    sca.simple_network_args(parser, 4000)
    parser.add_argument(
        "-d",
        "--device",
        default=None,
        help="Device serial number. Written on the device.",
    )
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    dev = VaunixSG(int(args.device))
    simple_server_loop({"vaunix_sg": dev}, sca.bind_address_from_args(args), args.port)


if __name__ == "__main__":
    main()
