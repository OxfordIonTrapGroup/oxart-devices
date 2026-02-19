#!/usr/bin/env python3
import argparse
import json
import logging
import time
from collections import OrderedDict

import sipyco.common_args as sca
from influxdb import InfluxDBClient
from sipyco.pc_rpc import Client

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("--influx-server",
                        default="localhost",
                        help="Influx server address")
    parser.add_argument("--database",
                        default="windfreaks",
                        help="Influx database name.")
    parser.add_argument("--name",
                        required=True,
                        help="Logical windfreak name, defines measurement name")
    parser.add_argument("--poll",
                        default=600,
                        type=int,
                        help="Measurement polling period (seconds)")
    parser.add_argument(
        "--config-file",
        help="Path toJSON config file defining parameters to monitor",
    )

    network_args = parser.add_argument_group("network server")
    network_args.add_argument(
        "-w",
        "--wf-server",
        default="localhost",
        help="Windfreak server hostname or IP address",
    )
    network_args.add_argument("--port",
                              default=4325,
                              type=int,
                              help="Server port to connect to")

    sca.verbosity_args(parser)

    return parser


def write_point(fields, name, influx_client):
    point = {"measurement": name, "fields": fields}
    try:
        logger.info("Writing point to InfluxDB: {}".format(point))
        influx_client.write_points([point])
    except ConnectionError:
        logger.error("ConnectionError: Influxdb down?")


def log_parameters(parameters, synth, influx_client, measurement_name):
    msg = {}
    control_instructions = parameters.get("control-instructions", {})
    primary_channel = control_instructions.get("primary_channel", None)

    for channel, config in parameters["channels"].items():
        synth.set_controlled_channel(channel)
        for key, cmd in config.items():
            msg[f"{channel}_{key}"] = synth.query_cmd(cmd)

    for key, cmd in parameters["device"].items():
        msg[key] = synth.query_cmd(cmd)

    if primary_channel is not None:
        synth.set_controlled_channel(primary_channel)

    write_point(msg, measurement_name, influx_client)


def parse_parameters(config_file):
    with open(config_file, "r") as json_file:
        logger.info(f"Loading parameters from {config_file}...")
        parameters = json.load(json_file, object_pairs_hook=OrderedDict)
        logger.debug(f"Loaded parameters to monitor: {parameters}")

    return parameters


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)
    parameters = parse_parameters(args.config_file)

    logger.info("Connecting to InfluxDB server at {}...".format(args.influx_server))
    influx_client = InfluxDBClient(host=args.influx_server,
                                   database=args.database,
                                   timeout=30)

    logger.info("Connecting to Windfreak SynthHD server at {}:{}...".format(
        args.wf_server, args.port))
    synthhd = Client(args.wf_server, args.port, "WindfreakSynthHD")
    logger.info("Connection established to Windfreak SynthHD server.")

    while True:
        log_parameters(parameters, synthhd, influx_client, args.name)
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
