#!/usr/bin/env python3.5

import argparse

from oxart.devices.thorlabs_mdt693a.driver import PiezoController
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the "
        "Thorlabs MDT693A 3-channel open-loop piezo controller"
    )
    sca.simple_network_args(parser, 9001)
    parser.add_argument(
        "-d", "--device", default=None, required=True, help="Device ip address"
    )
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = PiezoController(args.device)

    try:
        simple_server_loop({"piezoController": dev}, args.bind, args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
