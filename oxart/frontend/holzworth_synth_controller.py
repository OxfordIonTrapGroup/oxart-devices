#!/usr/bin/env python3.5

import argparse

from oxart.devices.holzworth_synth.driver import HolzworthSynth
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args


def get_argparser():
    parser = argparse.ArgumentParser(
        description=
        "ARTIQ controller for the Holzworth synth on the Quadrupole laser system")
    simple_network_args(parser, 4000)
    add_common_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = HolzworthSynth()  # Starts frequency update loop to track cavity drift

    try:
        simple_server_loop({"HolzworthSynth": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
