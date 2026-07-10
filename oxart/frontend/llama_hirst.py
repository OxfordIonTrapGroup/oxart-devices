#!/usr/bin/env python3
"""Continuously polls measurements from a USB connected GM08 gaussmeter.

Requires the gm08.dll file to be installed locally.
"""

from llama.influxdb import aggregate_stats_default
from llama.rpc import add_chunker_methods, run_simple_rpc_server
from llama.channels import ChunkedChannel
from oxart.devices.hirst_gaussmeter.driver import GaussMeter
import logging
import asyncio
import atexit

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 10e-3


def setup_args(parser):
    parser.add_argument(
        "--measurement",
        help="name of measurement; also used as InfluxDB series name",
        required=True,
    )
    parser.add_argument("-d",
                        "--device",
                        help="gm08 hardware address",
                        default=-1,
                        type=int)
    parser.add_argument(
        "--max-chunk-size",
        type=int,
        default=256,
        help=("number of measurements to average before sending " +
              "to InfluxDB (if not timed out first)"),
    )
    parser.add_argument(
        "--max-chunk-duration",
        type=float,
        default=30,
        help=("maximum wall-clock duration of averaging chunk before " +
              "sending to InfluxDB (if size not reached first)"),
    )


def setup_interface(args, influx_pusher, loop):
    device = GaussMeter(args.device)
    device.connect()

    def bin_finished(values):
        if influx_pusher:
            point = aggregate_stats_default(values)
            influx_pusher.push(args.measurement, point)
            logger.info(f"Pushing point: {args.measurement}: {point}")

    channel = ChunkedChannel(
        args.measurement,
        bin_finished,
        args.max_chunk_size,
        args.max_chunk_duration,
        loop,
    )

    async def poller_thread():
        while True:
            if device.has_new_data():
                value = device.get_latest_measurement()
                channel.push(value)
            else:
                # Don't spam the serial
                await asyncio.sleep(POLL_INTERVAL_S)

    logging_task = loop.create_task(poller_thread())

    def stop_logging_task():
        logging_task.cancel()
        try:
            loop.run_until_complete(logging_task)
        except asyncio.CancelledError:
            pass

    atexit.register(stop_logging_task)
    atexit.register(device.close)

    add_chunker_methods(device, channel)
    return device


def main():
    run_simple_rpc_server(4009, setup_args, "gaussmeter", setup_interface)


if __name__ == "__main__":
    main()
