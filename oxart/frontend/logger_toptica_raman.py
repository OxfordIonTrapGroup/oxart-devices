#!/usr/bin/env python3
import argparse
import asyncio
from asyncio import wait_for
import time
from influxdb import InfluxDBClient

from toptica.lasersdk.asyncio.dlcpro.v2_0_1 import Client, NetworkConnection


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
        help="Time (seconds) between messages from device after which connection is " +
        "considered faulty and program exits")
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
            print("ConnectionError: Influxdb down?")

    async def run():
        # Dictionary containing location of parameters in dlc
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
        msg = {key: None for key in parameters.keys()}
        async with Client(NetworkConnection(args.server)) as dlc:
            while True:
                time.sleep(args.poll)
                for key in parameters.keys():
                    try:
                        msg[key] = await wait_for(dlc.get(parameters[key], float),
                                                  timeout=args.timeout)
                    except Exception:
                        print('Error: Is DLC pro connected to network?')
                write_point(msg)

    loop.run_until_complete(run())


if __name__ == "__main__":
    main()
