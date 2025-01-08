#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.keysight_MSOX3104G.driver import MSOX3104G
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "Keysight InfiniiVision MSOX3104G")
    parser.add_argument(
        "-d",
        "--device",
        help="VISA address (e.g. 'USB0::0x2A8D::0x1787::CN58454180::0::INSTR')")

    sca.simple_network_args(parser, 4301)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = MSOX3104G(args.device)

    try:
        simple_server_loop({"MSOX3104G": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
