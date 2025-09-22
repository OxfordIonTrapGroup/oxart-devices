#!/usr/bin/env python3

import argparse

from oxart.devices.bme_pulse_picker.bme_delay_gen import ClockSource, Driver
from oxart.devices.bme_pulse_picker.timing import PulsePickerTiming
from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca


def get_argparser():
    parser = argparse.ArgumentParser(
        description="ARTIQ controller for BME delay generator PCI card")
    sca.simple_network_args(parser, 4007)
    parser.add_argument(
        "-s",
        "--simulation",
        default=False,
        action="store_true",
        help="Put the driver in simulation mode",
    )
    parser.add_argument("--allow-long-pulses", default=False, action="store_true")
    sca.verbosity_args(parser)
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    delay_gen = None
    if not args.simulation:
        delay_gen = Driver().init_single_pci_card()
        delay_gen.set_clock_source(ClockSource.external_80_mhz)

    timing = PulsePickerTiming(delay_gen, args.allow_long_pulses)
    try:
        simple_server_loop({"timing": timing}, args.bind, args.port)
    finally:
        timing.disable()


if __name__ == "__main__":
    main()
