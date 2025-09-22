#!/usr/bin/env python3.5

import argparse

from oxart.devices.sumitomo.driver import Sumitomo
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def main():
    parser = argparse.ArgumentParser(description="ARTIQ Helium compressor")
    sca.simple_network_args(parser, 2325)
    parser.add_argument("-d",
                        "--device",
                        help="IP address of controller",
                        required=True)
    sca.verbosity_args(parser)
    args = parser.parse_args()
    sca.init_logger_from_args(args)

    dev = Sumito(args.device)
    try:
        simple_server_loop({'Sumito': dev},sca.bind_address_from_args(args), args.port)
    except Exception:
        dev.close()    
    finally:
        dev.close()


if __name__ == "__main__":
    main()
