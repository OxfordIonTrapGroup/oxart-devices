#!/usr/bin/env python3

import argparse
import logging

import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop
from oxart.devices.agilent_33220a.driver import Agilent33220A


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for Agilent 33220a AWG"
    )
    parser.add_argument(
        "-d", "--device", default="10.255.6.26", help="IP address of device"
    )
    # parser.add_argument("-p",
    #                     "--port",
    #                     default="5025",
    #                     help="Port number of device")
    sca.simple_network_args(parser, 5025)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    logging.info(
        "Trying to establish connection "
        "to Agilent 33220A AWG at {}...".format(args.device)
    )
    dev = Agilent33220A(args.device, args.port)
    logging.info("Established connection.")

    try:
        logging.info("Starting server at port {}...".format(args.port))
        print("hello")
        simple_server_loop(
            {"Agilent33220A": dev}, sca.bind_address_from_args(args), args.port
        )
    finally:
        dev.close()


if __name__ == "__main__":
    main()
