import argparse

from oxart.devices.varian_multigauge.driver import VarianIonGauge
import sipyco.common_args as sca
from sipyco.pc_rpc import simple_server_loop


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--device",
        default="/dev/ttyUSB19",
        help="address (USB Serial Number or IP:port)",
    )
    sca.simple_network_args(parser, 5001)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    dev = VarianIonGauge(args.device)

    try:
        simple_server_loop(
            {"Varian_Multigauge": dev}, sca.bind_address_from_args(args), args.port
        )
    finally:
        dev.close()


if __name__ == "__main__":
    main()
