#!/usr/bin/env python3.5

import argparse

from oxart.devices.picomotor.driver import PicomotorController
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (simple_network_args, init_logger_from_args,
                                bind_address_from_args)
from oxart.tools import add_common_args


def main():
    parser = argparse.ArgumentParser(description="ARTIQ Picomotor controller")
    simple_network_args(parser, 4006)
    parser.add_argument("-d",
                        "--device",
                        help="IP address of controller",
                        required=True)
    add_common_args(parser)
    args = parser.parse_args()
    init_logger_from_args(args)

    dev = PicomotorController(args.device)
    try:
        simple_server_loop({'picomotorController': dev}, bind_address_from_args(args),
                           args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
