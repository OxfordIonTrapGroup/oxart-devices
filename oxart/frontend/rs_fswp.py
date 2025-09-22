import argparse
from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import (
    simple_network_args,
    init_logger_from_args,
    bind_address_from_args,
)
from oxart.tools import add_common_args
from oxart.devices.rs_fswp import RS_FSWP


def main():
    description = "RS FSWP Phase Noise Analyser controller"
    parser = argparse.ArgumentParser(description=description)
    simple_network_args(parser, 5001)
    add_common_args(parser)
    args = parser.parse_args()
    init_logger_from_args(args)

    dev = RS_FSWP()
    try:
        print("Running phase noise analyser server")
        simple_server_loop({"phase_noise_analyser": dev}, bind_address_from_args(args),
                           args.port)
    finally:
        dev.close()


if __name__ == "__main__":
    main()
