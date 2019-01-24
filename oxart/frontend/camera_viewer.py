import asyncio
import zmq
import zmq.asyncio
import pyqtgraph as pg
import numpy as np
import sys
import argparse
from PyQt5.QtWidgets import QApplication
from quamash import QEventLoop


async def recv_and_process(ctx, imv, args):
    sock = ctx.socket(zmq.SUB)
    sock.set_hwm(1)
    sock.connect("tcp://{}:{}".format(args.server, args.port))
    sock.setsockopt_string(zmq.SUBSCRIBE, args.serial)
    while True:
        # Receive camera serial number, which we have filtered on
        sn = await sock.recv_string()
        im = await sock.recv_pyobj()
        imv.setImage(im, autoRange=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", "-s", type=str, required=True)
    parser.add_argument("--port", "-p", type=int, default=5555)
    parser.add_argument("--serial", type=str, default="",
        help="Camera serial number to display images from. If not provided images from\
        all connected cameras will be displayed")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    ctx = zmq.asyncio.Context()

    imv = pg.ImageView()
    imv.show()

    # from matplotlib import cm
    # colormap = cm.get_cmap("nipy_spectral")
    # colormap._init()
    # lut = (colormap._lut * 255).view(np.ndarray)
    # imv.imageItem.setLookupTable(lut)

    try:
        loop.create_task(recv_and_process(ctx, imv, args))
        loop.run_forever()
    finally:
        loop.close()

if __name__ == "__main__":
    main()
