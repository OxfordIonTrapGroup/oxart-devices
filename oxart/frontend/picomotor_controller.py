#!/usr/bin/env python3.5

import argparse
import sys

from oxart.devices.picomotor.driver import PicomotorController
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import simple_network_args, init_logger, bind_address_from_args
from oxart.tools import add_common_args

def main():
    parser = argparse.ArgumentParser(description="ARTIQ Picomotor controller")
    simple_network_args(parser, 4006)
    parser.add_argument("-d", "--device",
                    help = "IP address of controller")
    add_common_args(parser)
    args = parser.parse_args()
    init_logger(args)

    if args.device is None:
        print("You need to specify -d/--device argument."
                                         "Use --help for more information.")
        sys.exit(1)

    dev = PicomotorController(args.device)
    try:
        simple_server_loop({'picomotorController':dev},
            bind_address_from_args(args), args.port)
    finally:
        dev.close()

if __name__ == "__main__":
    main()

