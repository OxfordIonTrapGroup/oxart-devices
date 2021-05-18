import argparse

from oxart.devices.brooks_4850.driver import Brooks4850
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d",
                        "--device",
                        default="socket://10.255.6.178:9001",
                        help="address (USB Serial Number or IP:port)")
    sca.simple_network_args(parser, 3255)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    dev = Brooks4850(args.device)

    try:
        simple_server_loop({"Brooks4850": dev}, sca.bind_address_from_args(args),
                           args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
