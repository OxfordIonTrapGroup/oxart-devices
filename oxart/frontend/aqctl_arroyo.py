#!/usr/bin/env python3

import argparse

import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop
from oxart.devices.arroyo.driver import Arroyo


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for Arroyo laser/TEC controllers")
    parser.add_argument("-d", "--device", help="hardware address of device")
    sca.simple_network_args(parser, 4310)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    dev = Arroyo(args.device)

    try:
        simple_server_loop({dev.id: dev}, sca.bind_address_from_args(args), args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
