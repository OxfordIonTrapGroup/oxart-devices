import sys
if sys.platform == 'win32':
    try:
        import win32com.client
    except:
        raise ImportError("win32com not found; consider 'pip install pywin32'")
else:
    raise RuntimeError("Platforms other than windows not supported")
import time

class OphirPowerMeter:
    """Interface to Ophir Starlite power meters"""
    def __init__(self, serial_number=None):
        # Initialise Ophir COM library as per the StarLab example code.
        self.com = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
        self.com.StopAllStreams()
        self.com.CloseAll()

        device_list = self.com.ScanUSB()
        if len(device_list) == 0:
            raise Exception("No Ophir power meter found")

        if serial_number is None and len(device_list) != 1:
            raise Exception("More than one Ophir power meter connected, "
                "specify a serial number", device_list)
        elif serial_number is None:
            serial_number = device_list[0][-1]

        self.device = self.com.OpenUSBDevice(serial_number)
        if not self.com.IsSensorExists(self.device, 0):
            raise Exception("No sensor connected to power meter")

    def start_acquisition(self):
        self.com.StartStream(self.device, 0)

    def get_latest_reading(self):
        while True:
            data = self.com.GetData(self.device, 0)
            if data[0]:
                break
            time.sleep(0.1)
        return data[0][-1]

    def modify_wavelength(self, wavelength, index=0, channel=0):
        self.com.ModifyWavelength(self.device, channel, index, wavelength)

    def set_wavelength(self, index=0, channel=0):
        self.com.SetWavelength(self.device, channel, index)

    def ping(self):
        return True

    def close(self):
        self.com.StopAllStreams()
        self.com.CloseAll()
        self.com = None
