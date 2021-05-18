import logging
import sys
if sys.platform == 'win32':
    try:
        import win32com.client
    except:
        raise ImportError("win32com not found; consider 'pip install pywin32'")
else:
    raise RuntimeError("Platforms other than windows not supported")
import time

logger = logging.getLogger(__name__)


class OphirPowerMeter:
    """Interface to Ophir Starlite power meters"""
    def __init__(self, serial_number=None, channel=0):
        self.channel = channel

        # Initialise Ophir COM library as per the StarLab example code.
        self.com = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")

        com_version = self.com.GetVersion()
        if com_version < 902:
            logger.warn("Ophir COM object version %s old and untested; "
                        "consider installing StarLab 3.40 or higher.")
        else:
            logger.info("Using Ophir COM object version %s.", com_version)

        self.com.StopAllStreams()
        self.com.CloseAll()

        device_list = self.com.ScanUSB()
        if len(device_list) == 0:
            raise Exception("No Ophir power meter found")

        self.device_serial_number = serial_number
        if self.device_serial_number is None:
            if len(device_list) != 1:
                raise Exception(
                    "More than one Ophir power meter connected, "
                    "specify a serial number", device_list)
            self.device_serial_number = device_list[-1]

        logger.info("Connecting to serial number %s...", self.device_serial_number)
        self.device = self.com.OpenUSBDevice(self.device_serial_number)

        if not self.com.IsSensorExists(self.device, self.channel):
            raise Exception("No sensor connected to power meter")
        self.sensor_serial_number, sensor_type, sensor_model = (self.com.GetSensorInfo(
            self.device, self.channel))
        logger.info("Connected; %s sensor (%s; serial number %s).", sensor_type,
                    sensor_model, self.sensor_serial_number)

    def start_acquisition(self):
        self.com.StartStream(self.device, self.channel)

    def stop_acquisition(self):
        self.com.StopAllStreams()

    def get_latest_reading(self):
        while True:
            data = self.com.GetData(self.device, self.channel)
            if data[0]:
                break
            time.sleep(0.1)
        return data[0][-1]

    def modify_wavelength(self, wavelength, index=0):
        self.com.ModifyWavelength(self.device, self.channel, index, wavelength)

    def set_wavelength(self, index=0):
        self.com.SetWavelength(self.device, self.channel, index)

    def get_range_names(self):
        """Return a list of power ranges supported by the sensor as
        human-readable strings.
        """
        _, range_names = self.com.GetRanges(self.device, self.channel)
        return range_names

    def set_range(self, r):
        """Select the given range.

        :param r: The range to select, given either as index into the
            array returned by :meth:`get_range_names`, or one of the strings.
        """
        if not isinstance(r, int):
            try:
                r = self.get_range_names().index(r)
            except ValueError:
                raise ValueError("Unsupported range '{}'".format(r))
        self.com.SetRange(self.device, self.channel, r)

    def get_device_serial_number(self):
        return self.device_serial_number

    def get_sensor_serial_number(self):
        return self.sensor_serial_number

    def ping(self):
        return True

    def close(self):
        self.com.StopAllStreams()
        self.com.CloseAll()
        self.com = None
