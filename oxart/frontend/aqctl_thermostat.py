#!/usr/bin/env python3

import atexit
import logging
import asyncio
from enum import Enum, unique

from llama.influxdb import aggregate_stats_default
from llama.rpc import add_chunker_methods, run_simple_rpc_server
from llama.channels import ChunkedChannel

from oxart.devices.thermostat.driver import Thermostat

logger = logging.getLogger(__name__)


@unique
class Measurement(Enum):
    adc = "adc (AD7172 input)"
    sens = "sens (thermistor resistance derived from adc)"
    temperature = "temperature (Steinhart-Hart conversion result derived from sens)"
    i_set = "i_set (TEC output current)"
    vref = "vref (MAX1968 VREF)"
    dac_value = "dac_value (AD5680 output derived from i_set)"
    dac_feedback = "dac_feedback (ADC measurement of the AD5680 output)"
    i_tec = "i_tec (MAX1968 TEC current monitor)"
    tec_i = "tec_i (TEC output current feedback derived from i_tec)"
    tec_u_meas = "tec_u_meas (measurement of the voltage across the TEC)"
    pid_output = "pid_output (PID control output)"


class RPCInterface(Thermostat):
    """Wraps Thermostat driver with llama functionality"""

    def __init__(self, influx_channels, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.influx_channels = influx_channels
        for channels in self.influx_channels:
            for c in channels.values():
                add_chunker_methods(self, c)

    def report_mode(self):
        """Method not supported by controller"""
        logger.exception("Report mode not supported by aqctl_thermostat controller.")

    def report(self):
        """Retrieve current status"""
        reports = super().report()
        # Always log the values to InfluxDB.
        if reports:
            for report in reports:
                idx = int(report.pop("channel"))
                for key, value in report.items():
                    try:
                        meas = Measurement[key]
                        self.influx_channels[idx][meas].push(float(value))
                    except (KeyError, TypeError):
                        # Ignore KeyError if Measurement with key does not exist.
                        # Ignore TypeError if value cannot be cast to float.
                        continue
        return reports

    async def _report_continuously(self, t_sleep):
        while True:
            await asyncio.sleep(t_sleep)
            self.report()


def setup_interface(args, influx_pusher, loop):
    influx_channels = [dict(), dict()]

    def reg_chan(meas_type: Measurement, idx) -> None:
        channel_name = f"{meas_type.name}_ch{idx}"

        def cb(values):
            if influx_pusher:
                influx_pusher.push(channel_name, aggregate_stats_default(values))

        influx_channels[idx][meas_type] = ChunkedChannel(channel_name, cb,
                                                         args.chunk_size, 30, loop)

    for i in range(len(influx_channels)):
        for meas in Measurement:
            reg_chan(meas, i)

    dev = RPCInterface(influx_channels, args.device)
    logging_task = loop.create_task(dev._report_continuously(args.poll_time))

    def stop_logging_task():
        logging_task.cancel()
        try:
            loop.run_until_complete(logging_task)
        except asyncio.CancelledError:
            pass

    atexit.register(stop_logging_task)
    return dev


def setup_args(parser):
    parser.description = "ARTIQ controller for Sinara Thermostat"
    parser.add_argument("-d", "--device", help="IP address of thermostat")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=256,
        help="Size of chunks logged to Grafana (max. 30 sec worth of samples)")
    parser.add_argument("--poll-time",
                        default=0.1,
                        type=float,
                        help="Seconds between measurements in chunk")


def main():
    run_simple_rpc_server(4060, setup_args, "thermostat", setup_interface)


if __name__ == "__main__":
    main()
