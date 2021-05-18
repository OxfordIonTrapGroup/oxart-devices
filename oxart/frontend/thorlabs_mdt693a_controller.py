#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.thorlabs_mdt693a.driver import PiezoController
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the "
        "Thorlabs MDT693A 3-channel open-loop piezo controller")
    simple_network_args(parser, 9001)
    parser.add_argument("-d",
                        "--device",
                        default=None,
                        required=True,
                        help="Device ip address")
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = PiezoController(args.device)

    try:
        simple_server_loop({"piezoController": dev}, args.bind, args.port)
    except Exception:
        dev.close()
    else:
        dev.close()
    finally:
        dev.save_setpoints()


if __name__ == "__main__":
    main()
