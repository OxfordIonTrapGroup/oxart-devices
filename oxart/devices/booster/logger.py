import argparse
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from requests.exceptions import ConnectionError

from oxart.devices.booster.driver import Booster


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True,
                        help="Booster IP address")
    parser.add_argument("--name", required=True,
                        help="logical Booster name, defines measurement name")
    parser.add_argument("--influx-server", default="10.255.6.4",
                        help="Influx server address")
    parser.add_argument("--database", default="junk",
                        help="Influx database name")
    return parser


def write(client, booster_name, measurement, data):
    point = {
        "measurement": booster_name,
        "tags": {
            "name": measurement,
            },
        "fields": {"ch{}".format(idx): value for idx, value in enumerate(data)}
    }
    try:
        client.write_points([point])
    except ConnectionError:
        print("ConnectionError: Influxdb down?")
    print(point)


def main():
    args = get_argparser().parse_args()

    client = InfluxDBClient(
            host=args.influx_server,
            database=args.database)

    dev = Booster(args.device)

    cmds = {"temp": "temp",
            "i_30V": "I29V",
            "i_6V": "I6V",
            "5V0MP": "V5VMP",
            "pwr_tx": "output_power",
            "pwr_rfl": "input_power"}

    while True:
        try:
            for key, value in cmds.items():
                data = [0]*8
                for channel in range(8):
                    status = dev.get_status(channel)
                    data[channel] = getattr(status, value)
                write(client, args.name, key, data)
        except InfluxDBClientError as e:
            print("Data error: {}".format(e))


if __name__ == "__main__":
    main()
