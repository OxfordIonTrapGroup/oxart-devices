import argparse
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (
    simple_network_args,
    verbosity_args,
    init_logger_from_args,
)
from oxart.devices.thorlabs_camera.driver import Camera, list_serials


def get_argparser():
    parser = argparse.ArgumentParser()
    simple_network_args(parser, 4000)
    verbosity_args(parser)
    parser.add_argument(
        "--list",
        action="store_true",
        help="list connected cameras (ignores all other arguments)",
    )
    parser.add_argument(
        "--device",
        "-d",
        type=int,
        default=None,
        help="camera serial number, uses first available if not supplied",
    )
    return parser


def run_server(dev, args):
    sn = dev.get_serial_no()
    try:
        simple_server_loop({"thorcam sn:{}".format(sn): dev}, args.bind, args.port)
    finally:
        dev.close()


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    if args.list:
        serials = list_serials()
        print(serials if serials else "No cameras found")
        return

    dev = Camera(sn=args.device)
    run_server(dev, args)


if __name__ == "__main__":
    main()
