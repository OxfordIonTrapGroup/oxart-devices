#!/usr/bin/env python3
import argparse
import json
import logging
import time

import sipyco.common_args as sca
from influxdb import InfluxDBClient
from sipyco.pc_rpc import Client

from oxart.devices.windfreak_synthhd.driver import SynthHDChannel

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--influx-server", default="localhost", help="Influx server address"
    )
    parser.add_argument(
        "--database", default="windfreaks", help="Influx database name."
    )
    parser.add_argument(
        "--name", required=True, help="Logical windfreak name, defines measurement name"
    )
    parser.add_argument(
        "--poll", default=600, type=int, help="Measurement polling period (seconds)"
    )

    sca.verbosity_args(parser)
    sca.simple_network_args(parser, 4325)

    return parser


def write_point(fields, name, influx_client):
    point = {"measurement": name, "fields": fields}
    try:
        influx_client.write_points([point])
    except ConnectionError:
        print("ConnectionError: Influxdb down?")


def log_parameters(parameters, synth, influx_client, measurement_name):
    msg = {}
    for channel in SynthHDChannel:
        with synth.control_channel(channel):
            for key, cmd in parameters[channel].items():
                msg[f"{channel.name}_{key}"] = synth.query_cmd(cmd)

    for key, cmd in parameters["device"].items():
        msg[key] = synth.query_cmd(cmd)
    write_point(msg, measurement_name, influx_client)


def parse_parameters(config_file):
    with open(config_file, "r") as json_file:
        logger.info(f"Loading parameters from {config_file}...")
        parameters = json.load(json_file)
        logger.debug(f"Loaded parameters to monitor: {parameters}")

    for channel in SynthHDChannel:
        parameters[channel] = parameters.pop(channel.name, {})

    return parameters


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    parameters = parse_parameters(args.config_file)

    logger.info("Connecting to InfluxDB server at {}...".format(args.influx_server))
    influx_client = InfluxDBClient(
        host=args.influx_server, database=args.database, timeout=30
    )
    logger.info("Connection established to InfluxDB server.")

    logger.info(
        "Connecting to Windfreak SynthHD server at {}:{}...".format(
            args.address, args.port
        )
    )
    synthhd = Client(args.address, args.port, "WindfreakSynthHD")
    logger.info("Connection established to Windfreak SynthHD server.")

    while True:
        time.sleep(args.poll)
        log_parameters(parameters, synthhd, influx_client, args.name)


if __name__ == "__main__":
    main()
