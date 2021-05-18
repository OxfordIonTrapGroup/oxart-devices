#!/usr/bin/env python3.5
import argparse
import zmq
import logging
import types

from sipyco.pc_rpc import simple_server_loop
from sipyco.common_args import simple_network_args, init_logger_from_args
from oxart.tools import add_common_args
import andorEmccd

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser()
    simple_network_args(parser, 4000)
    add_common_args(parser)
    parser.add_argument("--temp", default=-80, type=int)
    parser.add_argument("--broadcast-images", action="store_true")
    parser.add_argument("--zmq-bind", default="*")
    parser.add_argument("--zmq-port", default=5555, type=int)
    return parser


def create_zmq_server(bind="*", port=5555):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.set_hwm(1)
    socket.bind("tcp://{}:{}".format(bind, port))
    return socket


def main():
    args = get_argparser().parse_args()
    init_logger_from_args(args)

    def ping(self):
        # This raise an exception if the camera has been turned off, unplugged,
        # crashed, etc
        # self.get_temperature()
        return True

    logger.info("Initialising cameras...")
    cams = andorEmccd.initialise_all_cameras()
    if not cams:
        raise ValueError("No cameras found")
    logger.info("Done. Cameras serials: {}".format(", ".join(
        str(sn) for sn in list(cams.keys()))))

    for cam in cams.values():
        cam.ping = types.MethodType(ping, cam)

    if args.broadcast_images:
        socket = create_zmq_server(args.zmq_bind, args.zmq_port)
        for sn, cam in cams.items():

            def frame_callback(im, sn=sn):
                # We send a multi-part message with first part the serial number
                # this allows the subscriber to filter out unwanted images
                socket.send_string(str(sn), flags=zmq.SNDMORE)
                socket.send_pyobj(im)

            cam.register_callback(frame_callback)

    try:
        for cam in cams.values():
            cam.set_temperature(args.temp)
        # Target names must be strings
        simple_server_loop({str(k): v for k, v in cams.items()}, args.bind, args.port)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down cameras ...")
        for cam in cams.values():
            cam.close()


if __name__ == "__main__":
    main()
