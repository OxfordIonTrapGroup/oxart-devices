""" Driver for E4405B spectrum analysers """

import numpy as np

from oxart.devices.streams import get_stream


class E4405B:

    def __init__(self, device, timeout=10):
        self.stream = get_stream(device, timeout=timeout)
        assert self.ping()

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def ping(self):
        ident = self.identify().lower().split(",")
        ident = [sub_str.strip() for sub_str in ident]
        return ident[0:2] == ["hewlett-packard", "e4405b"]

    def close(self):
        self.stream.close()

    def find_peak(self, f0, freq, power, window=5.):
        """ Returns the index of the point with the highest power in the
        frequency range [f0-window/2.0, f0+window/2.0]. """

        lower_idx = np.argmin(np.abs(freq-(f0-window/2.)))
        upper_idx = np.argmin(np.abs(freq-(f0+window/2.)))

        peak = np.argmax(power[lower_idx:(upper_idx+1)]) + lower_idx
        return peak

    def get_sweep_axis(self):
        """ Returns a numpy array with the current frequency axis. """
        pts = self.get_sweep_pts()
        start = self.get_sweep_start()
        stop = self.get_sweep_stop()
        scale = self.get_sweep_scale()

        if scale == "lin":
            return np.linspace(start, stop, pts)
        elif scale == "log":
            return np.round(np.logspace(np.log10(start), np.log10(stop), pts))

    def set_sweep_span(self, span):
        """ Sets the frequency span in Hz. """
        self.stream.write("FREQ:SPAN {}\n".format(span).encode())

    def get_sweep_span(self):
        """ Returns the frequency span in Hz. """
        self.stream.write("FREQ:SPAN?\n".encode())
        return float(self.stream.readline().decode())

    def set_sweep_start(self, start):
        """ Sets the frequency sweep start in Hz. """
        self.stream.write("FREQ:START {}\n".format(start).encode())

    def get_sweep_start(self):
        """ Returns the frequency sweep start in Hz. """
        self.stream.write("FREQ:START?\n".encode())
        return float(self.stream.readline().decode())

    def set_sweep_stop(self, stop):
        """ Sets the frequency sweep stop in Hz. """
        self.stream.write("FREQ:STOP {}\n".format(stop).encode())

    def get_sweep_stop(self):
        """ Returns the frequency sweep stop in Hz. """
        self.stream.write("FREQ:STOP?\n".encode())
        return float(self.stream.readline().decode())

    def set_sweep_centre(self, centre):
        """ Sets the frequency sweep centre in Hz. """
        self.stream.write("FREQ:CENTER {}\n".format(centre).encode())

    def get_sweep_centre(self):
        """ Returns the frequency sweep centre in Hz. """
        self.stream.write("FREQ:CENTER?\n".encode())
        return float(self.stream.readline().decode())

    def set_sweep_pts(self, pts):
        """ Sets the number of points in the sweep. """
        self.stream.write("SWEEP:POINTS {:d}\n".format(pts).encode())

    def get_sweep_pts(self):
        """ Returns the number of points in the sweep. """
        self.stream.write("SWEEP:POINTS?\n".encode())
        return int(self.stream.readline().decode())

    def set_sweep_scale(self, scale):
        """ Sets the frequency scale to either "lin" or "log"."""
        if not scale.lower() in ["lin", "log"]:
            raise ValueError("Unrecognised fr equency scale.")
        self.stream.write("SWEEP:SPACING {}\n".format(scale.upper()).encode())

    def get_sweep_scale(self):
        """ Returns either "lin" or "log". """
        self.stream.write("SWEEP:SPACING?\n".encode())
        return self.stream.readline().decode().lower().strip()

    def get_bandwidth(self):
        """Retireves the resolution bandwidth in Hz"""
        self.stream.write("BANDWIDTH?\n".encode())
        return float(self.stream.readline().decode().lower().strip())

    def set_bandwidth(self, bwidth):
        """Specifies the resolution bandwidth in Hz"""
        self.stream.write("BANDWIDTH {}\n".format(bwidth).encode())
        return self.stream.readline().decode().lower().strip()

    def auto_bandwidth(self, select):
        '''Couples the resolution bandwidth to the frequency span.
        Select either 0, 1 for False/True'''
        self.stream.write("BANDWIDTH:AUTO {}\n".format(select).encode())
        return self.stream.readline().decode().lower().strip()

    def get_trace(self):
        """ Returns the current trace in the amplitude units.  """
        self.stream.write(":TRACE? TRACE1\n".encode())
        return np.array([
            float(pt) for pt in self.stream.readline().decode().split(',')])
