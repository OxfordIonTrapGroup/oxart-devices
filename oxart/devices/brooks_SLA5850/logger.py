import argparse
import logging
from datetime import datetime
import time
import json
import influxdb

import sipyco.common_args as sca
from sipyco.pc_rpc import Client
from oxart.devices.brooks_SLA5853.driver import BrooksSLA5853

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="Cryogenics logger",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-p",
                        "--poll-time",
                        help="time between measurements (s)",
                        type=int,
                        default=2)
    parser.add_argument("-db",
                        "--database",
                        help="influxdb database to log to",
                        default="comet")
    parser.add_argument("-a",
                        "--address",
                        help="ip address of flow controller",
                        default="10.179.22.99")
    parser.add_argument("port", help="port for flow controller", 
            type = int)
    sca.verbosity_args(parser)  # This adds the -q and -v handling
    return parser


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    dev = BrooksSLA5853(args.address, args.port)
    print("connected to SLA5853 flowmeter")

    # port = args.port
    # if port is None:
    #     devices = get_device_db(args.master)
    #     port = devices["cryostat"]["port"]

    while True:
        time.sleep(args.poll_time)
        with open("/home/ion/share/secrets/secret.json", "r") as f:
            secret = json.load(f)["influxdb"]

        try:
            influx = influxdb.InfluxDBClient(
                host=secret["host"],
                database=args.database,
                username=secret["username"],
                password=secret["password"])

            #flow_cont = Client(args.master, port, "LakeShore335")
            flow_cont = BrooksSLA5853(args.address, args.port)
            try:
                assert flow_cont.ping(), "Cannot connect to device"
                flow, flow_unit, temperature, temp_unit = flow_cont.read_flow_rate_and_temperature()
            finally:
                flow_cont.close_connection()

            influx.write_points([{
                "measurement": "cryo",
                "fields": {
                    "large_flow": flow
                }}])

            logger.info("{} - Cryogen flow rate: {}l/min".format(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), flow))

        except Exception as err:
            logger.warning("{}".format(err))
        finally:
            influx.close()


if __name__ == "__main__":
    main()
