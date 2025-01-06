import argparse

from oxart.devices.brooks_SLA5853.driver import BrooksSLA5853
from sipyco.pc_rpc import simple_server_loop
import asyncio
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(description = "Controller for Brooks SLA5853 flowmeter")
    sca.simple_network_args(parser, 3336)
    parser.add_argument(
        "-d",
        "--ip_address",
        default="10.179.22.99",
        help="IP address of serial-to-ethernet box")
    parser.add_argument("port", default=9001, help = "port of flowmeter", type = int)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    dev = BrooksSLA5853(args.ip_address, args.port)

    try:
        simple_server_loop({"BrooksSLA5853": dev},
                           sca.bind_address_from_args(args),
                           args.port,
                           loop=asyncio.get_event_loop())
    finally:
        dev.close_connection()


if __name__ == "__main__":
    main()
