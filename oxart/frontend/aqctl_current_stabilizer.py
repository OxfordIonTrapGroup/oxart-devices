#!/usr/bin/env python3

import argparse
import asyncio
import logging

from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.devices.stabilizer.current_stabilizer import Stabilizer
from oxart.tools import add_common_args

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for stabilizer_current_sense controller")
    parser.add_argument("-d", "--device", help="Device IP address")

    simple_network_args(parser, 4300)
    add_common_args(parser)
    return parser


async def open_connections(device_host):
    fb = await asyncio.open_connection(host=device_host, port=1235)
    ff = await asyncio.open_connection(host=device_host, port=1237)
    return fb, ff


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    loop = asyncio.get_event_loop()
    fb, ff = loop.run_until_complete(open_connections(args.device))
    dev = Stabilizer(fb, ff)

    simple_server_loop({"stabilizer_current_sense": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
