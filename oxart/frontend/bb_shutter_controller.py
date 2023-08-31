#!/usr/bin/env python3.5

import argparse

from oxart.devices.bb_shutter.driver import BBShutter
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the BeagleBone 4-channel shutter driver")
    sca.simple_network_args(parser, 4000)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = BBShutter()

    simple_server_loop({"bbShutter": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
