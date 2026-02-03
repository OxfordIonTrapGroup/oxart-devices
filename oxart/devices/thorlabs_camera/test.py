from .driver import *
import atexit


def main():
    cam = Camera()
    atexit.register(cam.disconnect)
    cam.open()
    cam.get_sensor_info_str()
    cam.disconnect()


if __name__ == "__main__":
    main()
