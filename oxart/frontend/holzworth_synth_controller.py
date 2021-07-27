#!/usr/bin/env python3.5

import argparse

from oxart.devices.holzworth_synth.driver import HolzworthSynth
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the Holzworth synth "
        "on the Quadrupole laser system")
    sca.simple_network_args(parser, 4000)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = HolzworthSynth()  # Starts frequency update loop to track cavity drift

    try:
        simple_server_loop({"HolzworthSynth": dev}, args.bind, args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
