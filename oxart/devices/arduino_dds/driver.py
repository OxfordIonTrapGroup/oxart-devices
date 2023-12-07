import time
import serial
import logging

logger = logging.getLogger(__name__)


def _write_exactly(f, data):
    remaining = len(data)
    pos = 0
    while remaining:
        written = f.write(data[pos:])
        remaining -= written
        pos += written


class ProfileDescriptor:

    def __init__(self, freq_word, amp_word, phase_word):
        self.freq_word = freq_word
        self.amp_word = amp_word
        self.phase_word = phase_word

    def __repr__(self):
        return "({},{},{})".format(self.freq_word, self.amp_word, self.phase_word)

    def __eq__(self, value):
        if value is None:
            return False

        if not isinstance(value, ProfileDescriptor):
            raise ValueError("Bad value type in ProfileDescriptor equality: "
                             "{}".format(type(value)))

        if self.freq_word == value.freq_word and\
           self.amp_word == value.amp_word and\
           self.phase_word == value.phase_word:
            return True
        else:
            return False


class ArduinoDDS:
    lsb_amp = 1.0 / 16383  # 0x3fff is maximum amplitude
    lsb_phase = 360.0 / 65536  # Degrees per LSB.

    def __init__(self, addr, clock_freq):
        # addr : serial port name
        # clock_freq : clock frequency in Hz

        self.ser = serial.Serial(addr, baudrate=115200)
        self.lsb_freq = clock_freq / (2**32)
        self.clock_freq = clock_freq
        time.sleep(5)
        logger.info("Connected to ArduinoDDS with ID '{}'".format(self.identity()))

        # List of currently set profiles
        self.current_profiles = [None] * 8

    def send(self, data):
        self.ser.write(data.encode())

    def set_profile(self, profile, freq, phase=0.0, amp=1.0):
        """Sets a DDS profile frequency (Hz), phase (degrees), and
        amplitude (full-scale). Phase defaults to 0 and amplitude
        defaults to 1
        """

        if amp < 0 or amp > 1:
            raise ValueError("DDS amplitude must be between 0 and 1")

        # This should be dependant on the clock frequency
        if freq < 0 or freq > 450e6:
            raise ValueError("DDS frequency must be between 0 and 450 MHz")

        amp_word = int(round(amp / self.lsb_amp))
        phase_word = int(round((phase % 360.0) / self.lsb_phase))
        freq_word = int(round(freq / self.lsb_freq))

        new_profile = ProfileDescriptor(freq_word, amp_word, phase_word)

        # Check if this profile is already present
        if self.current_profiles[profile] == new_profile:
            logger.debug("Not setting profile {} with {}, already set"
                         "".format(profile, new_profile))
        else:
            # If it is not present, set it and log it
            self._set_profile_lsb(profile, freq_word, phase_word, amp_word)
            self.current_profiles[profile] = new_profile
            logger.debug("Setting profile {} with {}".format(profile, new_profile))

    def _set_profile_lsb(self, profile, freq, phase, amp):
        """Freq, phase, amp are all in units of lsb"""
        if profile < 0 or profile > 7 or not isinstance(profile, int):
            raise ValueError("DDS profile should be an integer between 0 and 7")
        if amp > 0x3fff or amp < 0 or not isinstance(amp, int):
            raise ValueError("DDS amplitude word should be an integer "
                             "between 0 and 0x3fff")
        if phase > 0xffff or phase < 0 or not isinstance(phase, int):
            raise ValueError("DDS phase word should be an integer between "
                             "0 and 0xffff")
        if freq < 0 or freq > 0xffffffff or not isinstance(freq, int):
            raise ValueError("DDS frequency word should be an integer "
                             "between 0 and 0xffffffff")

        self.send('PLSB {} {} {} {}\n'.format(profile, amp, phase, freq))
        time.sleep(0.01)

    def reset(self):
        self.send("reset\n")

    def identity(self):
        self.send("*IDN?\n")
        return self.ser.readline().decode().strip()

    def ping(self):
        return True


class ArduinoDDSSim:
    lsb_amp = 1.0 / 16383  # 0x3fff is maximum amplitude
    lsb_phase = 360.0 / 65536  # Degrees per LSB.
    lsb_freq = (2**32) / 1e9

    def __init__(self):
        pass

    def set_profile(self, profile, freq, phase=0.0, amp=1.0):
        pass

    def set_profile_lsb(self, profile, freq, phase, amp):
        """Freq, phase, amp are all in units of lsb"""
        pass

    def reset(self):
        pass

    def identity(self):
        return "ident"

    def ping(self):
        return True
