from artiq.experiment import *
import time
from oitg.imaging.roi_tools import *


class CameraSetup(EnvExperiment):
    """Set camera parameters."""
    _camera_name = "camera"

    def build(self):
        self.camera = self.get_device(self._camera_name)
        self.setattr_device("ccb")

        self.t_exp = self.get_argument("Exposure", NumberValue(50 * ms, unit="ms"))
        self.en_em_gain = self.get_argument("EM enabled", BooleanValue(default=False))
        self.em_gain = self.get_argument("EM Gain", NumberValue(default=300))

        self.roi_mode = self.get_argument("Image size",
                                          EnumerationValue(["Full", "ROI"]))
        self.run_acq = self.get_argument("Start acquisition", BooleanValue())

        self.set_default_scheduling(pipeline_name="camera")

    def run(self):
        self.issue_applets()

        self.camera.stop_acquisition()
        self.camera.set_trigger_mode(0)

        if self.roi_mode == "Full":
            self.camera.set_image_region(0, 511, 0, 511)
        else:
            roi = self.get_dataset("camera.roi")
            self.camera.set_image_region(*roi)

        self.camera.set_exposure_time(self.t_exp)

        if self.en_em_gain:
            self.camera.set_horizontal_shift_parameters(17,
                                                        em_gain=True,
                                                        adc_bit_depth=16)
        else:
            self.camera.set_horizontal_shift_parameters(3,
                                                        em_gain=False,
                                                        adc_bit_depth=16)
        self.camera.set_vertical_shift_speed(3.3)
        self.camera.set_em_gain(self.em_gain)

        if self.run_acq:
            self.camera.start_acquisition()

    def issue_applets(self):
        ddb = self.get_device_db()
        dev = ddb[self._camera_name]

        self.ccb.issue("create_applet",
                       "Camera",
                       "${python} -m oxart.applets.camera_viewer "
                       "--server " + dev["host"] + " "
                       "--serial " + dev["target_name"],
                       group="monitor")


class ChooseROI(EnvExperiment):
    """Set camera ROI."""

    def build(self):
        self.setattr_device("core")
        self.setattr_device("camera")

        self.roi_length = \
            self.get_argument("ROI length", NumberValue(50, ndecimals=0))
        self.roi_width = \
            self.get_argument("ROI width", NumberValue(50, ndecimals=0))

        self.ion_signal_width = \
            self.get_argument("Ion signal width", NumberValue(30, ndecimals=0))

        self.set_default_scheduling(pipeline_name="camera")

    def run(self):
        self.camera.stop_acquisition()
        self.camera.set_trigger_mode(0)
        self.camera.set_image_region(0, 511, 0, 511)
        self.camera.set_exposure_time(50 * ms)

        self.camera.flush_images()

        self.camera.start_acquisition(single=True)
        while True:
            im_full = self.camera.get_image()
            if im_full is not None:
                break
            time.sleep(10 * ms)

        im, sub_region = trim_image(im_full,
                                    n_width=int(self.roi_width),
                                    n_length=int(self.roi_length))

        roi = [*sub_region[0], *sub_region[1]]

        roi_clipped = []
        for r in roi:
            if r > 511:
                r = 511
            if r < 0:
                r = 0
            roi_clipped.append(r)

        ion_regions = find_ion_regions(im, max_width=int(self.ion_signal_width))

        self.set_dataset("camera.im_full", im_full, broadcast=True)
        self.set_dataset("camera.im", im.copy())
        self.set_dataset("camera.roi", roi_clipped, broadcast=True)
        self.set_dataset("camera.ion_regions", ion_regions, broadcast=True)
