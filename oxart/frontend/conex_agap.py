import argparse

from conex_agap.driver import ConexMirror
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (simple_network_args, init_logger_from_args,
                                bind_address_from_args)
from oxart.tools import add_common_args


def main():
    parser = argparse.ArgumentParser(description="Conex AGAP mirror controller")
    simple_network_args(parser, 5000)
    parser.add_argument("-d",
                        "--device",
                        help="Hardware address of controller",
                        required=True)
    parser.add_argument("--id", required=True, help="Controller ID")
    add_common_args(parser)
    args = parser.parse_args()
    init_logger_from_args(args)

    dev = ConexMirror(args.id, args.device)
    try:
        simple_server_loop({'conex_agap': dev}, bind_address_from_args(args),
                           args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
