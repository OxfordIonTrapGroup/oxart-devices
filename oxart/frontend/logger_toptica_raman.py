#!/usr/bin/env python3
import argparse
import asyncio
import logging
import time
from influxdb import InfluxDBClient
from toptica.lasersdk.asyncio.dlcpro.v2_0_1 import Client, NetworkConnection

logger = logging.getLogger(__name__)

# Maps user-facing parameter names (used for InflxuDB fields) to the DLC pro's internal
# ones.
parameters = {
    "dl-current-act": "laser1:dl:cc:current-act",
    "dl-voltage-act": "laser1:dl:cc:voltage-act",
    "dl-temp-act": "laser1:dl:tc:temp-act",
    "amp-current-act": "laser1:amp:cc:current-act",
    "amp-voltage-act": "laser1:amp:cc:voltage-act",
    "amp-temp-act": "laser1:amp:tc:temp-act",
    "amp-seed-power": "laser1:amp:pd:seed:power",
    "amp-power": "laser1:amp:pd:amp:power",
    "shg-temp-act": "laser1:nlo:shg:tc:temp-act",
    "shg-power": "laser1:nlo:pd:shg:power"
}


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s",
                        "--server",
                        required=True,
                        help="Laser controller address / hostname")
    parser.add_argument("--name",
                        required=True,
                        help="Logical laser name, defines measurement name")
    parser.add_argument("--influx-server",
                        default="localhost",
                        help="Influx server address")
    parser.add_argument("--database",
                        default="lab_1_toptica_raman",
                        help="Influx database name")
    parser.add_argument("--poll",
                        default=30,
                        type=int,
                        help="Measurement polling period (seconds)")
    parser.add_argument(
        "--timeout",
        default=60,
        type=int,
        help="Timeout for controller responses before which connection " +
        "is considered faulty and reconnection is attempted.")
    return parser


def main():
    args = get_argparser().parse_args()
    loop = asyncio.get_event_loop()

    influx_client = InfluxDBClient(host=args.influx_server,
                                   database=args.database,
                                   timeout=30)

    def write_point(fields):
        point = {"measurement": args.name, "fields": fields}
        try:
            influx_client.write_points([point])
        except ConnectionError:
            logger.exception("ConnectionError: InfluxDB down?")

    async def run_poll_loop():
        async with Client(NetworkConnection(args.server)) as dlc:
            next_update = time.monotonic()
            while True:
                await asyncio.sleep(next_update - time.monotonic())
                next_update += args.poll
                msg = {key: None for key in parameters.keys()}
                for key in parameters.keys():
                    msg[key] = await asyncio.wait_for(dlc.get(parameters[key], float),
                                                      timeout=args.timeout)
                write_point(msg)

    async def run():
        while True:
            try:
                await run_poll_loop()
            except Exception:
                logger.exception("Is DLC pro connected to network?")
                # Ignore exception and retry after a while.
                await asyncio.sleep(args.poll)

    loop.run_until_complete(run())


if __name__ == "__main__":
    main()
