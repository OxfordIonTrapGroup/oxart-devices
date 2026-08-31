#!/usr/bin/env python3

import argparse
import asyncio

from oxart.devices.holzworth_synth.driver import HolzworthSynth
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for the Holzworth synth "
        "on the Quadrupole laser system")
    parser.add_argument("--config-file",
                        default=None,
                        help="JSON file holding the drift ramp state (default: "
                        "alongside the driver source)")
    parser.add_argument("--update-interval",
                        default=10.,
                        type=float,
                        help="interval between drift ramp frequency updates, in "
                        "seconds (default: %(default)s)")
    sca.simple_network_args(parser, 4000)
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    dev = HolzworthSynth(config_file=args.config_file,
                         update_interval=args.update_interval)
    try:
        # Starts the frequency update loop to track the cavity drift; must run on the
        # same event loop as the server below.
        loop.run_until_complete(dev.start())
        try:
            simple_server_loop({"HolzworthSynth": dev},
                               sca.bind_address_from_args(args),
                               args.port,
                               loop=loop)
        finally:
            loop.run_until_complete(dev.stop())
    finally:
        dev.close()
        loop.close()


if __name__ == "__main__":
    main()
