#!/usr/bin/env python3
import argparse
import asyncio
import time
import importlib
import logging
import json
from asyncio import wait_for
from influxdb import InfluxDBClient

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("-s",
                        "--dlc-server",
                        required=True,
                        help="Laser controller address / hostname.")
    parser.add_argument("--firmware",
                        default="v3_0_1",
                        help="Firmware version of DLC Pro")
    parser.add_argument("--name",
                        required=True,
                        help="Logical laser name, defines measurement name")
    parser.add_argument("--influx-server",
                        default="localhost",
                        help="Influx server address")
    parser.add_argument("--database",
                        default="dl_pro_status",
                        help="Influx database name.")
    parser.add_argument("--poll",
                        default=30,
                        type=int,
                        help="Measurement polling period (seconds)")
    parser.add_argument("--config-file",
                        help="Path to json file configuring parameters to monitor.")
    parser.add_argument("-v",
                        "--verbose",
                        help="Increase output verbosity",
                        action="count",
                        default=0)

    parser.add_argument(
        "--timeout",
        default=60,
        type=int,
        help="Time (seconds) between messages from device after which connection is " +
        "considered faulty and program exits",
    )
    return parser


def setup_logging(verbose_arg):
    levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    level = levels[min(verbose_arg, len(levels) - 1)]  # cap to last level index
    logging.basicConfig(level=level)


def main():
    args = get_argparser().parse_args()

    setup_logging(args.verbose)

    # Import corresponding DLC Pro module for the required firmware
    dlcpro_sdk = importlib.import_module(
        ".lasersdk.asyncio.dlcpro.{}".format(args.firmware), "toptica")

    # Get the parameters to monitor from config file
    with open(args.config_file, 'r') as json_file:
        logger.info(f"Loading parameters from {args.config_file}...")
        parameters = json.load(json_file)
        logger.debug(f"Loaded parameters to monitor: {parameters}")

    loop = asyncio.get_event_loop()
    influx_client = InfluxDBClient(host=args.influx_server,
                                   database=args.database,
                                   timeout=30)

    def write_point(fields):
        point = {"measurement": args.name, "fields": fields}
        try:
            influx_client.write_points([point])
        except ConnectionError:
            print("ConnectionError: Influxdb down?")

    async def stream_data():
        msg = {key: None for key in parameters.keys()}
        logger.info("Connecting to DLC Pro...")
        while True:
            async with dlcpro_sdk.Client(dlcpro_sdk.NetworkConnection(
                    args.dlc_server)) as dlc:
                logger.info("Established connection to DLC Pro")
                while True:
                    time.sleep(args.poll)
                    for key in parameters.keys():
                        try:
                            msg[key] = await wait_for(dlc.get(parameters[key], float),
                                                      timeout=args.timeout)
                        except Exception as exception:
                            logger.error(
                                f"Is DLC pro connected to network?: {exception}")
                            break
                    else:
                        write_point(msg)
                        continue
                    break
            logger.warning("Connection to DLC Pro lost. Trying to reconnect...")

    loop.run_until_complete(stream_data())


if __name__ == "__main__":
    main()
