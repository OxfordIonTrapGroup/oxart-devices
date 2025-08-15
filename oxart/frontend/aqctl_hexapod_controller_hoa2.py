#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.hex_controller_C88752_hoa2.driver import Hexapod
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "PI Hexapod Controller C-887.52 in HOA2")
    parser.add_argument("-d", "--device", help="Hexapod's IP address")
    parser.add_argument("--safety-case", type=str, help="Safety case string.")
    parser.add_argument("--safety-data", type=float, nargs="*", help="Space-separated list of floats for safety data.")
    parser.add_argument("--critical-points-data", type=float, nargs="*", help="Space-separated list of floats for critical points data.")

    sca.simple_network_args(parser, 4302)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = Hexapod(args.device, args.safety_case, args.safety_data, args.critical_points_data)

    try:
        simple_server_loop({"Hexapod Controller": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
