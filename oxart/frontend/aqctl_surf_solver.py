#!/usr/bin/env python3.5

import argparse

from oxart.devices.surf_solver.driver import SURF
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for SURF")
    simple_network_args(parser, 4000)
    add_common_args(parser)
    parser.add_argument("--load_path", default=None,
                        help="path to trap data file")
    parser.add_argument("--user", default="Comet",
                        help="User preset")
    return parser


def main():
    print("starting controller")
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    dev = SURF(args.user, args.load_path)

    simple_server_loop({"SURF_"+args.user: dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
