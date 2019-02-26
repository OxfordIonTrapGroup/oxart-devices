#!/usr/bin/env python3

import argparse
import sys

from artiqDrivers.devices.bme_pulse_picker.bme_delay_gen import ClockSource, Driver
from artiqDrivers.devices.bme_pulse_picker.timing import PulsePickerTiming
from artiq.protocols.pc_rpc import simple_server_loop
from artiq.tools import verbosity_args, simple_network_args, init_logger


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--simulation", default=False, action="store_true",
                        help="Put the driver in simulation mode")
    parser.add_argument("--allow-long-pulses", default=False, action="store_true")

    simple_network_args(parser, 4007)
    verbosity_args(parser)
    return parser

def main():
    args = get_argparser().parse_args()
    init_logger(args)

    delay_gen = None
    if not args.simulation:
        delay_gen = Driver().init_single_pci_card()
        delay_gen.set_clock_source(ClockSource.external_80_mhz)

    timing = PulsePickerTiming(delay_gen, args.allow_long_pulses)
    simple_server_loop({"timing": timing}, args.bind, args.port)

if __name__ == "__main__":
    main()
