import serial
import argparse
from influxdb import InfluxDBClient
from requests.exceptions import ConnectionError


def parse_status_table(lines):
    """Parse the status table into a dictionary with parameter names as keys, 
    with values being vectors of parameter values over the channels.
    An example line of the table is:
    IN8V0 [mA]\t0.039\t0.018\t0.013\t0.021\t0.008\t0.109\t0.008\t0.010
    """
    status = {}
    for line in lines:
        # The description can contain spaces, so we special case this
        _DESC_LEN = 16
        desc = line[:_DESC_LEN].strip()

        parts = line.strip().split("\t")
        desc = parts[0]
        ch_parts = parts[1:]

        # Skip the channel number template
        if len(desc) == 0:
            continue
        chs = [p for p in ch_parts if len(p)>0 ]

        try:
            vals = [float(x) for x in chs]
        except ValueError:
            vals = chs
        status[desc] = vals
    return status



def get_messages(h):
    in_block = False
    lines = []

    while True:
        line = h.readline().decode()

        contains_marker = line.startswith("="*70)

        if in_block:
            if contains_marker:
                # If the marked block is long enough to contain a valid table ...
                if len(lines) > 20:
                    in_block = False
                    status = parse_status_table(lines)
                    yield status
                else:
                    # Treat this as a start marker rather than an end marker
                    in_block = True
                lines = []
            else:
                lines.append(line)

        if not in_block and contains_marker:
            in_block = True



def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, 
        help="Device serial port address")
    parser.add_argument("--name", required=True, 
        help="logical Booster name, defines measurement name")
    parser.add_argument("--influx-server", default="10.255.6.4",
        help="Influx server address")
    parser.add_argument("--database", default="junk", 
        help="Influx database name")
    return parser

def write_point(args, client, name, fields, tags={}):
    point = {
        "measurement": args.name,
        "tags": {
            "name": name,
            },
        "fields": fields
    }
    for tag in tags:
        point["tags"][tag] = tags[tag]
    try:
        client.write_points([point])
    except ConnectionError:
        print("ConnectionError: Influxdb down?")


def main():
    args = get_argparser().parse_args()

    client = InfluxDBClient(
            host=args.influx_server,
            database=args.database)

    h = serial.Serial(args.device)

    # Ensure the logging task is running
    h.write("start\r\n".encode());

    for status in get_messages(h):
        def write_channels(name, values):
            fields = {}
            for i, v in enumerate(values):
                fields["ch{}".format(i)] = v
            write_point(args, client, name, fields)

        write_channels("temp", [(x+y)/2 for x,y in zip(status["LTEMP"],status["RTEMP"])])
        write_channels("i_30V", status["I30V [A]"])
        write_channels("i_6V", status["I6V0 [A]"])
        write_channels("i_n8V", status["IN8V0 [mA]"])
        write_channels("on", status["ON"])
        write_channels("son", status["SON"])
        write_channels("ovc", status["OVC"])
        write_channels("pwr_tx", status["TXPWR [dB]"])
        write_channels("pwr_rfl", status["RFLPWR [dB]"])
        try:
            write_channels("v_mp", status["5V0MP [V]"])
        except KeyError:
            pass


if __name__ == "__main__":
    main()