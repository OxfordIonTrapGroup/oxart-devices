#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.lakeshore_335.driver import LakeShore335
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for Lake "
        "Shore Cryogenics model 335 temperature"
        "controllers"
    )
    parser.add_argument(
        "-d",
        "--device",
        default="gpib://socket://10.255.6.189:1234-5",
        help="device's hardware address",
    )

    sca.simple_network_args(parser, 4300)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = LakeShore335(args.device)

    try:
        simple_server_loop(
            {"LakeShore335": dev}, sca.bind_address_from_args(args), args.port
        )
    finally:
        dev.close()


if __name__ == "__main__":
    main()
