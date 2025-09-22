#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.rs_zvl.driver import RS_ZVL
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller RS ZVL VNA")
    parser.add_argument(
        "-d",
        "--device",
        help="IP address of RS ZVL")

    sca.simple_network_args(parser, 9903)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = RS_ZVL(args.device)

    try:
        simple_server_loop({"RS_ZVL": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
