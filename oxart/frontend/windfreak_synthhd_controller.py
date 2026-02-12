#!/usr/bin/env python3

import argparse
import logging

import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop

from oxart.devices.windfreak_synthhd.driver import WindfreakSynthHD

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for Windfreak SynthHD signal generator",
    )
    parser.add_argument(
        "--serial-port", help="Serial port for Windfreak SynthHD", required=True
    )

    sca.simple_network_args(parser, 4310)
    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    with WindfreakSynthHD(args.serial_port) as synthhd:
        logger.info("Starting server at port {}...".format(args.port))
        simple_server_loop(
            {"WindfreakSynthHD": synthhd}, sca.bind_address_from_args(args), args.port
        )


if __name__ == "__main__":
    main()
