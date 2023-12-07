import argparse
import math
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from requests.exceptions import ConnectionError

from oxart.devices.booster.driver import Booster

from serial import SerialTimeoutException


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, help="Booster IP address")
    parser.add_argument("--name",
                        required=True,
                        help="logical Booster name, defines measurement name")
    parser.add_argument("--influx-server",
                        default="10.255.6.4",
                        help="Influx server address")
    parser.add_argument("--database", default="junk", help="Influx database name")
    return parser


def write(client, booster_name, measurement, data):
    data = [0.0 if math.isnan(pt) else pt for pt in data]
    point = {
        "measurement": booster_name,
        "tags": {
            "name": measurement,
        },
        "fields": {
            "ch{}".format(idx): value
            for idx, value in enumerate(data)
        }
    }
    try:
        client.write_points([point])
    except ConnectionError:
        print("ConnectionError: Influxdb down?")


def main():
    args = get_argparser().parse_args()

    client = InfluxDBClient(host=args.influx_server, database=args.database)

    dev = Booster(args.device)
    # vcp = BoosterVCP('/dev/ttyACM0')

    # print(vcp.get_version())
    # print("ethernet status:")
    # for line in vcp.get_eth_diag():
    #     print("  ", line)
    # print("logstash:")
    # for line in vcp.get_logstash():
    #     print("  ", line)

    cmds = {
        "temp": "temp",
        "i_30V": "I29V",
        "i_6V": "I6V",
        "5V0MP": "V5VMP",
        "pwr_tx": "output_power",
        "pwr_rfl": "input_power"
    }

    ind = 0
    while True:
        try:
            for key, value in cmds.items():
                data = [0] * 8
                for channel in range(8):
                    status = dev.get_status(channel)
                    data[channel] = getattr(status, value)
                write(client, args.name, key, data)
            ind += 1

        except (InfluxDBClientError, SerialTimeoutException) as e:
            print("exception after {} iterations: {}".format(ind, e))
            # print(vcp.get_version())
            # print("ethernet status:")
            # for line in vcp.get_eth_diag():
            #     print("  ", line)
            # print("logstash:")
            # for line in vcp.get_logstash():
            #     print("  ", line)
            # ind = 0
            break


if __name__ == "__main__":
    main()
