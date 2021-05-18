from .driver import *
import atexit


def main():
    o = OphirPowerMeter()
    atexit.register(o.close)
    o.modify_wavelength(422)
    o.set_wavelength()
    o.start_acquisition()
    print(o.get_latest_reading())


if __name__ == "__main__":
    main()
