#!/usr/bin/env python3.5

import argparse

import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop

from oxart.devices.decomposer.driver import Decomposer, Result

def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for Gate Decomposer")
    sca.simple_network_args(parser, 4001)
    sca.verbosity_args(parser)
    parser.add_argument("--threads", default=1,
                        help="Tell julia how many threads to use for optimisation (relatively unexplored feature: Are the threads constantly allocated? How much faster is it?)")
    parser.add_argument("--cache_path", default=None,
                        help="path on which to cache results. `None` (default) disables the cache.")
    return parser

def main():
    print("Starting gate decomposer...")

    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    # Start decomposer
    dev = Decomposer(args.threads, args.cache_path)

    simple_server_loop({"GateDecomposer_controller": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()