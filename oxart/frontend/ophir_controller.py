#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.ophir.driver import OphirPowerMeter
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import (verbosity_args, simple_network_args, init_logger,
                                                    bind_address_from_args)

def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the "
                                    "Ophir power meter")
    simple_network_args(parser, 4000)
    parser.add_argument("-d", "--device", default=None,
                        help="Device serial number. This is the unit no., "
                        "not that of the sensor")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = OphirPowerMeter(args.device)

    simple_server_loop({"ophir": dev}, bind_address_from_args(args), args.port)


if __name__ == "__main__":
    main()
