#!/usr/bin/env python3
import time
import argparse
import asyncio
from influxdb import InfluxDBClient

from oxart.devices.solstis.driver import SolstisNotifier


def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", required=True, 
        help="Laser controller address / hostname")
    parser.add_argument("--name", required=True, 
        help="Logical laser name, defines measurement name")
    parser.add_argument("--influx-server", default="localhost", 
        help="Influx server address")
    parser.add_argument("--database", default="solstis", 
        help="Influx database name")
    parser.add_argument("--poll", default=30, type=int,
        help="Measurement polling period (seconds)")
    return parser

def main():
    args = get_argparser().parse_args()
    loop = asyncio.get_event_loop()

    influx_client = InfluxDBClient(
        host=args.influx_server,
        database=args.database)

    def write_point(fields, tags={}):
        point = {
            "measurement": args.name,
            "fields": fields
        }
        for tag in tags:
            point["tags"][tag] = tags[tag]
        try:
            influx_client.write_points([point])
        except ConnectionError:
            print("ConnectionError: Influxdb down?")

    def handle_status_update(msg):
        t = time.time()
        if t < handle_status_update.last_status_update + args.poll:
            return
        handle_status_update.last_status_update = t
        fields = {
            "doubler_output_pd": float(msg["ECD_output_mon"]),
            "laser_output_pd": float(msg["output_monitor"]),
            "resonator_pzt": float(msg["resonator_voltage"]),
            "etalon_pzt": float(msg["etalon_voltage"]),
            "doubler_pzt": float(msg["doubler_voltage"]),
            "cavity_lock_status": msg["cavity_lock_status"],
            "doubler_lock_status": msg["doubler_lock_status"],
            "etalon_lock_status": msg["etalon_lock_status"],
            "brf_wavelength": float(msg["wsd_wavelength"])
        }
        write_point(fields)
    handle_status_update.last_status_update = 0

    def handle_notification(msg):
        if msg["display_notification"] != 1:
            return
        if msg["notification_message"] in \
                ["Saved Vapour Cell Items",
                "Saved Sprout Items",
                "Saved Beam Alignment Setup",
                "Saved Scope Setup",
                "Saved Stitching Setup",
                "Saved Wavelength Meter Setup",
                "Saved Common Items"]:
            return
        fields = {
            "title": msg["notification_message"],
            "tags": args.name
        }
        write_point(fields, tags={"type":"display_notification"})

    notifier = SolstisNotifier(
        server=args.server,
        notification_callback=handle_notification,
        status_callback=handle_status_update
    )
    loop.run_until_complete(notifier.run())


if __name__ == "__main__":
    main()