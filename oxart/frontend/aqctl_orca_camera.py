#!/usr/bin/env python3.5
import argparse
import zmq
import logging

from sipyco.pc_rpc import simple_server_loop
import sipyco.common_args as sca
from orca_camera.driver import OrcaFusion

logger = logging.getLogger(__name__)


def get_argparser():
    parser = argparse.ArgumentParser()
    sca.simple_network_args(parser, 4000)
    sca.verbosity_args(parser)
    parser.add_argument("--broadcast-images", default=True, action="store_true")
    parser.add_argument("--zmq-bind", default="*")
    parser.add_argument("--zmq-port", default=5555, type=int)
    parser.add_argument("--roi", default="884,200,956,48")
    parser.add_argument("--buffer-size", default=10000, type=int)
    parser.add_argument("--speed",
                        default=3,
                        type=int,
                        help="integer value - (1: QUIET, 2: STANDARD, 3: FAST)")
    parser.add_argument("--exposure_time",
                        default=0.1,
                        type=float,
                        help="default exposure time in seconds")
    return parser


def create_zmq_server(bind="*", port=5555):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.set_hwm(1)
    socket.bind("tcp://{}:{}".format(bind, port))
    return socket


def main():
    args = get_argparser().parse_args()
    sca.init_logger_from_args(args)

    logger.info("Initialising cameras...")

    roi = [int(x) for x in args.roi.split(",")]
    assert (len(roi) == 4)

    dev = OrcaFusion()
    dev.open(camera_index=0, framebuffer_len=args.buffer_size)
    dev.set_subarray(*roi)
    dev.set_readout_speed(args.speed)
    dev.set_exposure_time(args.exposure_time)
    dev.start_capture()

    if args.broadcast_images:
        socket = create_zmq_server(args.zmq_bind, args.zmq_port)

        def frame_callback(im):
            # We send a multi-part message with first part the serial number
            # this allows the subscriber to filter out unwanted images
            socket.send_string(str(0), flags=zmq.SNDMORE)
            socket.send_pyobj(im.transpose())

        dev.register_callback(frame_callback)

    try:
        simple_server_loop({"camera": dev}, args.bind, args.port)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down camera ...")
        dev.close()


if __name__ == "__main__":
    main()
