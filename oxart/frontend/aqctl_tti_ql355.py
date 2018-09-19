#!/usr/bin/env python3.5

import argparse
import logging

from oxart.devices.streams import address_args, get_stream
from oxart.devices.tti_ql355.driver import QL355

from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args
from artiq.tools import init_logger, bind_address_from_args

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for "
                                     "TTI QL355P (TP) single (triple) channel"
                                     " power supplies")
    simple_network_args(parser, 4006)
    verbosity_args(parser)
    address_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)
    dev = QL355(get_stream(args, baudrate=19200, port=9221, timeout=0.1))

    # Q: Why not use try/finally for port closure?
    # A: We don't want to try to close the serial if sys.exit() is called,
    #    and sys.exit() isn't caught by Exception
    try:
        simple_server_loop({"ql355": dev}, bind_address_from_args(args),
                           args.port)
    except Exception:
        dev.close()
    else:
        dev.close()


if __name__ == "__main__":
    main()
