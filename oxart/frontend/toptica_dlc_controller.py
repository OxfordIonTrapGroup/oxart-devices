#!/usr/bin/env python3

import asyncio
import argparse
import logging
import importlib
from oxart.devices.toptica_dlc.driver import TopticaDLC
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca
import warnings

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description=
        "ARTIQ controller to read lock status from TopticaDLCpro with lock module")

    parser.add_argument("--dlc-server",
                        required=True,
                        help="Laser controller address / hostname.")

    sca.simple_network_args(parser, 4305)

    parser.add_argument("--firmware",
                        default="v3_0_1",
                        help="Firmware version of DLC Pro")
    parser.add_argument(
        "--timeout",
        default=10,
        type=int,
        help="Time (seconds) between messages from device after which connection is " +
        "considered faulty and program exits",
    )

    sca.verbosity_args(parser)

    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dlcpro_sdk = importlib.import_module(
        ".lasersdk.asyncio.dlcpro.{}".format(args.firmware), "toptica")

    dlc = dlcpro_sdk.Client(dlcpro_sdk.NetworkConnection(args.dlc_server))

    dlc_driver = TopticaDLC(dlc, args.timeout)

    # suppress DepracationWarning on get_event_loop
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        loop = asyncio.get_event_loop()

    loop.run_until_complete(dlc_driver.open())
    print(" :: Connection established", dlc)

    try:
        simple_server_loop({"Lock Status Controller": dlc_driver},
                           args.bind,
                           args.port,
                           loop=loop)
    finally:
        loop.run_until_complete(dlc_driver.close())


if __name__ == "__main__":
    main()
