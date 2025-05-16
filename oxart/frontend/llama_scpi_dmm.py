#!/usr/bin/env python3
"""
Continuously polls measurements from a SCPI-enabled digital multimeter, logs the results
to InfluxDB, and also provides an ARTIQ controller interface.

The multimeter settings (measurement type, range, etc.) are expected to already be
configured appropriately and will not be changed by this program.
"""

from llama.influxdb import aggregate_stats_default
from llama.rpc import add_chunker_methods, run_simple_rpc_server
from llama.channels import ChunkedChannel
from oxart.devices.scpi_dmm.driver import ScpiDmm
import logging
import threading

logger = logging.getLogger(__name__)


def setup_args(parser):
    parser.add_argument("-d",
                        "--device",
                        help="multimeter hardware address",
                        required=True)
    parser.add_argument("--measurement",
                        help="name of measurement; also used as InfluxDB series name",
                        required=True)
    parser.add_argument("--max-chunk-size",
                        type=int,
                        default=256,
                        help=("number of measurements to average before sending " +
                              "to InfluxDB (if not timed out first)"))
    parser.add_argument("--max-chunk-duration",
                        type=float,
                        default=30,
                        help=("maximum wall-clock duration of averaging chunk before " +
                              "sending to InfluxDB (if size not reached first)"))


def setup_interface(args, influx_pusher, loop):
    device = ScpiDmm(args.device)

    def bin_finished(values):
        if influx_pusher:
            influx_pusher.push(args.measurement, aggregate_stats_default(values))

    channel = ChunkedChannel(args.measurement, bin_finished, args.max_chunk_size,
                             args.max_chunk_duration, loop)

    def poller_thread():
        while True:
            device.initiate_measurement()
            value = device.fetch_result()
            loop.call_soon_threadsafe(lambda: channel.push(value))

    threading.Thread(target=poller_thread, daemon=True).start()

    class RPCInterface:
        # Could expose more driver methods in the future (but then need to coordinate
        # with poller thread).
        pass

    rpc_interface = RPCInterface()
    add_chunker_methods(rpc_interface, channel)
    return rpc_interface


def main():
    run_simple_rpc_server(4009, setup_args, "llama_scpi_dmm", setup_interface)


if __name__ == "__main__":
    main()
