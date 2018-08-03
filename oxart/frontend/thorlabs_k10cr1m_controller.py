#!/usr/bin/env python3.5

import argparse
import sys
from threading import Thread

from oxart.devices.thorlabs_k10cr1m.driver import K10CR1MDriver
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger

def incomplete_network_args(parser):
    """like simple_network_args but without port"""
    group = parser.add_argument_group("network server")
    group.add_argument(
        "--bind", default=[], action="append",
        help="additional hostname or IP addresses to bind to; "
        "use '*' to bind to all interfaces (default: %(default)s)")
    group.add_argument(
        "--no-localhost-bind", default=False, action="store_true",
        help="do not implicitly also bind to localhost addresses")


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ controller for the Thorlabs K10CR1/M motorised rotation mount")
    # simple_network_args(parser, 4002)
    incomplete_network_args(parser)

    parser.add_argument('-c', '--controllers', type=int, nargs=2, action='append',
        help="Supply -c/--controllers [serial-number] [port] for each controller")
    verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    for tup in args.controllers:
        sn = tup[0]
        port = tup[1]
        dev = K10CR1MDriver(sn=sn)

        t = Thread(target=simple_server_loop,
                   args=({"k10cr1/m": dev}, args.bind, port))
        t.start()

if __name__ == "__main__":
    main()
