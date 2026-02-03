#!/usr/bin/env python3.5

import argparse

from oxart.devices.surf_solver.driver import SURF
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for SURF")
    sca.simple_network_args(parser, 4000)
    sca.verbosity_args(parser)
    parser.add_argument(
        "--trap_model_path",
        default="/home/ion/scratch/julia_projects/" "SURF/trap_model/comet_model.jld",
        help="path to the SURF trap model file",
    )
    parser.add_argument(
        "--cache_path",
        default=None,
        help="path on which to cache results. `None` (default)" " disables the cache.",
    )
    return parser


def main():
    print("starting controller")
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = SURF(args.trap_model_path, args.cache_path)

    simple_server_loop({"SURF_controller": dev}, args.bind, args.port)


if __name__ == "__main__":
    main()
