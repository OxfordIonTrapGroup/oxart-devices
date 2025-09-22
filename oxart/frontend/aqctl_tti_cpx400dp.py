#!/usr/bin/env python3

import argparse
import logging

from oxart.devices.tti_cpx400dp.driver import CPX400DP

from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (bind_address_from_args, init_logger_from_args,
                                simple_network_args, verbosity_args)

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "TTI CPX400DP dual channel power supply")
    simple_network_args(parser, 4006)
    verbosity_args(parser)
    parser.add_argument("-d", "--device", help="power supply IP address", required=True)
    parser.add_argument("--port",
                        help="TCP port (default: 9221)",
                        type=int,
                        default=9221)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = CPX400DP(args.device, port=args.port)

    try:
        simple_server_loop({"cpx400dp": dev}, bind_address_from_args(args), args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
