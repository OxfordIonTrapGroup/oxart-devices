#!/usr/bin/env python3.5

import argparse

from oxart.devices.picomotor.driver import PicomotorController
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def main():
    parser = argparse.ArgumentParser(description="ARTIQ Picomotor controller")
    sca.simple_network_args(parser, 4006)
    parser.add_argument("-d",
                        "--device",
                        help="IP address of controller",
                        required=True)
    sca.verbosity_args(parser)
    args = parser.parse_args()
    sca.init_logger_from_args(args)

    dev = PicomotorController(args.device)
    try:
        simple_server_loop({'picomotorController': dev},
                           sca.bind_address_from_args(args), args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
