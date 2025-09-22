#!/usr/bin/env python3

import argparse
import logging

import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop
from oxart.devices.agilent_6671a.driver import Agilent6671A


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for Agilent 6671A PSU")
    parser.add_argument(
        "-d",
        "--device",
        default="gpib://socket://10.255.6.10:1234-0",
        help="hardware address of device",
    )
    sca.simple_network_args(parser, 4310)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    logging.info("Trying to establish connection "
                 "to Agilent 6671A PSU at {}...".format(args.device))
    dev = Agilent6671A(args.device)
    logging.info("Established connection.")

    try:
        logging.info("Starting server at port {}...".format(args.port))
        simple_server_loop({"Agilent6671A": dev}, sca.bind_address_from_args(args),
                           args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
