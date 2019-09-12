import argparse
import logging
from datetime import datetime
import time
import influxdb

from artiq.tools import add_common_args, init_logger
from artiq.protocols.pc_rpc import Client

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        description="Cryogenics logger",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-p", "--poll-time",
                        help="time between measurements (s)",
                        type=int,
                        default=5)
    parser.add_argument("-db", "--database",
                        help="influxdb database to log to",
                        default="comet")
    parser.add_argument("-a", "--address", help="address of flow controller",
                        default="10.255.6.178")
    parser.add_argument("-p", "--port", help="port for flow controller",
                        default="9001")
    add_common_args(parser)  # This adds the -q and -v handling
    return parser


def main():
    args = get_argparser().parse_args()
    init_logger(args)

    while True:
        try:
            time.sleep(args.poll_time)

            influx = influxdb.InfluxDBClient(
                host="10.255.6.4",
                database=args.database,
                username="admin",
                password="admin")

            flow_cont = Client(args.address, args.port,
                               "BrooksMassFlowController4850")
            try:
                assert flow_cont.ping(), "Cannot connect to device"
                flow = flow_cont.read_flow()
            finally:
                flow_cont.close_rpc()

            influx.write_points([{
                "measurement": "cryo_T",
                "fields": {
                    "Flow": flow
                }}])

            logger.info("{} - Cryostat flow: {}".format(
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), flow))

        except Exception as err:
            logger.warning("{}".format(err))
        finally:
            influx.close()


if __name__ == "__main__":
    main()
