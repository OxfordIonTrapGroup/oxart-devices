#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.bb_shutter.driver import BBShutter
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger

def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the BeagleBone 4-channel shutter driver")
    simple_network_args(parser, 4000)
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    dev = BBShutter()

    simple_server_loop({"bbShutter": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
