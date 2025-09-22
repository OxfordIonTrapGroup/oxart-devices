from pylablib.devices import Thorlabs
import logging

logger = logging.getLogger(__name__)


def list_serials():
    return Thorlabs.list_cameras_tlcam()


class Camera(Thorlabs.ThorlabsTLCamera):
    """Driver for Thorlabs cameras based on pylablib ThorlabsTLCamera class.

    See parent class documentation for more details on available methods.
    """

    def __init__(self, sn=None):
        super().__init__(serial=sn)

    def open(self):
        super().open()
        logger.warning("Camera connected")
        logger.warning(self.get_device_info_str())
        logger.warning(self.get_sensor_info_str())

    def get_serial_no(self):
        return self.serial

    def get_device_info_str(self):
        return repr(super().get_device_info())

    def get_sensor_info_str(self):
        return repr(super().get_sensor_info())

    def wait_for_frame(self,
                       since="now",
                       nframes=1,
                       timeout=20.0,
                       error_on_stopped=False):
        super().wait_for_frame(
            since=since,
            nframes=nframes,
            timeout=timeout,
            error_on_stopped=error_on_stopped,
        )

    def get_frame(self, timeout=5.0):
        if not self.acquisition_in_progress():
            logger.warning("Acquisition not running, starting it.")
            self.start_acquisition()
        self.wait_for_frame(timeout=timeout)
        return super().read_newest_image()

    def get_multiple_frames(self, nframes=5, timeout=5.0):
        if not self.acquisition_in_progress():
            logger.warning("Acquisition not running, starting it.")
            self.start_acquisition()

        self.wait_for_frame(nframes=nframes + 1, timeout=timeout)
        return super().read_multiple_images(rng=(-nframes, -1))

    def disconnect(self):
        if self.acquisition_in_progress():
            self.stop_acquisition()
        self.close()

    def set_exposure_ms(self, exp):
        super().set_exposure(exp / 1000.0)

    def set_gain_dB(self, gain_dB, truncate=False):
        super().set_gain(gain_dB, truncate)

    def get_gain_dB(self):
        return super().get_gain()

    def get_gain_range_dB(self):
        return super().get_gain_range()

    def set_roi(self, hstart=260, hend=800, vstart=0, vend=50, hbin=1, vbin=1):
        """Warning! This seems to be inconsistent up to some pixels
        in the vertical axis. Don't forget to check the roi limits
        with self.get_roi_limits(). The region of interest
        should be larger than the min value and smaller than the max
        (the size of the detector). Check with self.get_roi() to see
        the effective frame size.
        """
        super().set_roi(hstart=hstart,
                        hend=hend,
                        vstart=vstart,
                        vend=vend,
                        hbin=hbin,
                        vbin=vbin)

    def get_roi_limits_dict(self, hbin=1, vbin=1):
        """Override parent class to output a dictionary.
        [LV] I believe sipyco does not allow some object
        types passing through the server.
        """
        xlim, ylim = super().get_roi_limits(hbin, vbin)
        limits = {
            "xlim": {
                "min": xlim.min,
                "max": xlim.max,
                "pstep": xlim.pstep,
                "sstep": xlim.sstep,
                "maxbin": xlim.maxbin,
            },
            "ylim": {
                "min": ylim.min,
                "max": ylim.max,
                "pstep": ylim.pstep,
                "sstep": ylim.sstep,
                "maxbin": ylim.maxbin,
            },
        }
        return limits

    def reset_roi_max(self):
        limits = self.get_roi_limits_dict()
        xlim_max = limits["xlim"]["max"]
        ylim_max = limits["ylim"]["max"]
        self.set_roi(0, xlim_max, 0, ylim_max)

    def ping(self):
        """Needed to run inside ARTIQ control manager."""
        return True
