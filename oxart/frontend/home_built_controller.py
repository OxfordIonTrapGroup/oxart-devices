#!/usr/bin/env python3

import atexit
import asyncio

from llama.influxdb import aggregate_stats_default
from llama.rpc import add_chunker_methods, run_simple_rpc_server
from llama.channels import ChunkedChannel
from oxart.devices.home_built_controller.driver import (
    TemperatureController,
    MeasurementType,
)


class RPCInterface:

    def __init__(self, dev, channels):
        self.dev = dev
        self.channels = channels
        for c in self.channels.values():
            add_chunker_methods(self, c)

    def set_pid_parameters(self, *args, **kwargs):
        return self.dev.set_pid_parameters(*args, **kwargs)

    def set_current(self, *args, **kwargs):
        return self.dev.set_current(*args, **kwargs)

    def enable_pid(self, *args, **kwargs):
        return self.dev.enable_pid(*args, **kwargs)

    async def _run_logging(self):
        while True:
            result = self.dev.get_measurement()
            for meas_type, meas_value in result.items():
                if meas_type in self.channels:
                    self.channels[meas_type].push(float(meas_value))
            await asyncio.sleep(0.2)


def setup_interface(args, influx_pusher, loop):
    channels = dict()

    def reg_chan(meas_type: MeasurementType) -> None:

        def cb(values):
            if influx_pusher:
                influx_pusher.push(meas_type.value, aggregate_stats_default(values))

        channels[meas_type] = ChunkedChannel(meas_type.name, cb, 256, 30, loop)

    reg_chan(MeasurementType.temperature)
    reg_chan(MeasurementType.current)

    dev = TemperatureController(args.device)
    atexit.register(dev.close)

    interface = RPCInterface(dev, channels)

    logging_task = loop.create_task(interface._run_logging())

    def stop_logging_task():
        logging_task.cancel()
        try:
            loop.run_until_complete(logging_task)
        except asyncio.CancelledError:
            pass

    atexit.register(stop_logging_task)

    return interface


def setup_args(parser):
    parser.add_argument("device", help="Serial device")


def main():
    run_simple_rpc_server(4059, setup_args, "home_built_controller", setup_interface)


if __name__ == "__main__":
    main()
