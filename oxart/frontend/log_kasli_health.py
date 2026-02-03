#!/usr/bin/env python3
"""Reads the Kasli FPGA on-die temperature/voltage sensors and writes them to
InfluxDB.

This relies on a JTAG connection (usually via the micro-USB port on the front panel).
"""

import argparse
from influxdb import InfluxDBClient
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device-serial",
        required=True,
        help="Kasli serial number (as passed to OpenOCD, e.g. kasli_105)",
    )
    parser.add_argument(
        "--device-name",
        required=True,
        help="Logical Kasli name as used for InfluxDB tag",
    )
    parser.add_argument(
        "--influx-server", default="10.255.6.4", help="InfluxDB server address"
    )
    parser.add_argument(
        "--database", default="fpga_health", help="InfluxDB database name"
    )
    args = parser.parse_args()

    script = [
        "source [find board/kasli.cfg]",
        f"ftdi_serial {args.device_serial}",
        "init",
        "xadc_report xc7.tap",
        "exit",
    ]
    result = subprocess.run(
        ["openocd", "-c", ";".join(script)], encoding="utf-8", capture_output=True
    )
    if result.returncode != 0:
        print("OpenOCD call failed:", result)

    data = {}
    for line in result.stderr.splitlines():
        frags = line.split(" ")
        if frags[0] in ("TEMP", "VCCINT", "VCCAUX", "VCCBRAM"):
            data[frags[0].lower()] = float(frags[1])

    influx_client = InfluxDBClient(
        host=args.influx_server, database=args.database, timeout=10
    )
    influx_client.write_points(
        [
            {
                "measurement": "xc7_xadc",
                "fields": data,
                "tags": {"name": args.device_name},
            }
        ]
    )


if __name__ == "__main__":
    main()
