#!/usr/bin/env python3.5
import argparse
from textwrap import dedent
from typing import Dict, Any, List, Callable

import toml
import zmq
import logging

from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca
from orca_camera.driver import OrcaFusion, LibInstance

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser(
        epilog=dedent("""\
            Example configuration file:
            ```
            [system1]
            serial = "S/N: 123456"
            broadcast_images = true
            roi = [884, 200, 956, 48]
            speed = 2
            
            [system2]
            serial = "S/N: 456789"
            ```
            
            The serial must match the string provided by the device exactly.
        """)
    )
    sca.simple_network_args(parser, 4000)
    sca.verbosity_args(parser)
    parser.add_argument("--broadcast-images", default=True, action="store_true")
    parser.add_argument("--zmq-bind", default="*")
    parser.add_argument("--zmq-port", default=5555, type=int)
    parser.add_argument("--roi", default="884,200,956,48")
    parser.add_argument("--speed",
                        default=3,
                        type=int,
                        help="integer value - (0: QUIET, 1: STANDARD, 2: FAST)")
    parser.add_argument(
        "--config-file",
        help="Path to TOML configuration file that allows setting serial, roi, "
             "speed and broadcast_images for multiple cameras."
    )
    return parser


def lazy_zmq_server(bind="*", port=5555):
    socket = None

    def create_zmq_server():
        nonlocal socket
        if socket is None:
            context = zmq.Context()
            socket = context.socket(zmq.PUB)
            socket.set_hwm(1)
            socket.bind("tcp://{}:{}".format(bind, port))
        return socket

    return create_zmq_server


def init_dev(
        name: str,
        args: Dict[str, Any],
        devs: List[OrcaFusion],
        create_zmq_server: Callable[[], Any],
) -> OrcaFusion:

    if args["serial"] is None and len(devs) != 1:
        raise ValueError(
            f"Multiple cameras present but no serial set for {name}. Camera "
            f"serials present: {', '.join(repr(dev.get_serial()) for dev in devs)}"
        )
    elif args["serial"] is None and len(devs) == 1:
        dev = devs[0]
    else:
        for idx, dev in enumerate(devs):
            if dev.get_serial() == args["serial"]:
                break
        else:
            raise ValueError(
                f"Unable to find camera with serial number {args['serial']} for "
                f"{name}. Camera serials present: "
                f"{', '.join(repr(dev.get_serial()) for dev in devs)}"
            )
        # Remove the matched device so that we don't reference the same device
        # twice with different arguments
        del devs[idx]

    if "roi" in args:
        dev.set_subarray(*args["roi"])
    if "speed" in args:
        dev.set_readout_speed(args["speed"])
    dev.start_capture()

    if args.get("broadcast_images", False):
        socket = create_zmq_server()

        def frame_callback(im):
            # We send a multi-part message with first part the serial number
            # this allows the subscriber to filter out unwanted images
            socket.send_string(dev.get_serial(), flags=zmq.SNDMORE)
            socket.send_pyobj(im.transpose())

        dev.register_callback(frame_callback)

    return dev


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    logger.info("Initialising cameras...")

    if args.config_file:
        config = toml.load(args.config_file)
    else:
        roi = [int(x) for x in args.roi.split(",")]
        if len(roi) != 4:
            raise ValueError("--roi should be 4 comma separated numbers")

        config = {
            "camera": {
                "serial": None,
                "broadcast_images": args.broadcast_images,
                "roi": roi,
                "speed": args.speed,
            }
        }

    devs = [
        OrcaFusion(idx, framebuffer_len=1000)
        for idx in range(LibInstance.get().num_dev)
    ]
    all_devs = devs.copy()
    create_zmq_server = lazy_zmq_server(args.zmq_bind, args.zmq_port)

    servers = {
        name: init_dev(name, args, devs, create_zmq_server)
        for name, args in config.items()
    }

    try:
        simple_server_loop(servers, args.bind, args.port)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down camera ...")
        for dev in all_devs:
            dev.close()


if __name__ == "__main__":
    main()
