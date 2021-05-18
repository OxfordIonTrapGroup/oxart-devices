# see https://www.keysight.com/upload/cmc_upload/All/Infiniium_prog_guide.pdf

import serial
import numpy as np


def to_nsd(data, t_axis):
    """ Convert data from time domain to frequency domain with noise
    spectral density units.

    Normalization ensures that rms(data) = sum()
    """
    num_bins = int(len(data) / 2)
    amplitudes = np.fft.fft(data)[0:num_bins] / num_bins
    nsd = amplitudes / np.sqrt(2)

    freq_ax = np.fft.fftfreq(len(data), t_axis[1] - t_axis[0])

    td_rms = np.sqrt(np.mean(np.power(data - np.mean(data), 2)))
    fd_rms = np.sqrt(sum(np.power(np.abs(nsd[1:]), 2)))
    assert (td_rms - fd_rms) / td_rms < 1e-10

    return freq_ax[0:num_bins], nsd


class MSO_S:
    """ Driver for Keysight MSO-S mixed-signal scopes """
    def __init__(self, ip):
        self.dev = serial.serial_for_url("socket://{}:5025".format(ip))

    def get_waveform(self):
        """ Returns waveform data from the scope's memory.

        Does not trigger a measurement (see the root-level ':RUN' and ':DIG'
        commands for that).
        """
        self.dev.write(":WAV:DATA?\n".encode())
        return np.array(self.dev.readline().decode().strip('\n,\r ').split(','),
                        dtype=np.float32)

    def get_x_axis(self):
        """ Returns an x-axis with a given number of points """
        self.dev.write(":WAV:POIN?\n".encode())
        num_pts = int(self.dev.readline().decode().strip())
        self.dev.write(":WAV:XOR?\n".encode())
        origin = float(self.dev.readline().strip())

        self.dev.write(":WAV:XINC?\n".encode())
        inc = float(self.dev.readline().strip())

        return np.arange(num_pts) * inc + origin
