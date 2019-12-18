#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.lakeshore_335.driver import LakeShore335
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for Lake "
                                     "Shore Cryogenics model 335 temperature"
                                     "controllers")
    parser.add_argument("-d", "--device", help="device's hardware address")

    simple_network_args(parser, 4300)
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = LakeShore335(args.device)

    try:
        simple_server_loop({"LakeShore335": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
