#!/usr/bin/env python3.5

import argparse
import logging

from oxart.devices.tti_ql355.driver import QL355

from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (bind_address_from_args, init_logger_from_args,
                                simple_network_args, verbosity_args)

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "TTI QL355P (TP) single (triple) channel"
                                     " power supplies")
    simple_network_args(parser, 4006)
    verbosity_args(parser)
    parser.add_argument("-d",
                        "--device",
                        help="device's hardware address",
                        required=True)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)
    dev = QL355(args.device)

    # Q: Why not use try/finally for port closure?
    # A: We don't want to try to close the serial if sys.exit() is called,
    #    and sys.exit() isn't caught by Exception
    try:
        simple_server_loop({"ql355": dev}, bind_address_from_args(args), args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
