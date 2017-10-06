import logging
import ctypes
import numpy as np

logger = logging.getLogger(__name__)

class HolzworthSynth():

    def __init__(self):

        self.dll = ctypes.WinDLL("HolzworthHS1001.dll")

        self.dll.getAttachedDevices.restype = ctypes.c_char_p

        self.serialnum = self.dll.getAttachedDevices()

        if self.serialnum.decode() == '':
            raise Exception("No devices connected")

        rc = self.dll.openDevice(self.serialnum)
        assert(rc>0)

        self.dll.usbCommWrite.restype = ctypes.c_char_p

        self.suffix_dict = {'Hz':1,'kHz':1e3,'MHz':1e6,'GHz':1e9} # SI suffixes
        self.multiplier_dict = {v: k for k, v in self.suffix_dict.items()} # swap keys for values

    def get_freq(self,limits=0):
        """Returns the current set frequency of the Holzworth synth when called without arguments or limits=0
        , and returns the maximum and minimum allowed frequency when called with limits=1 and limits =-1 respectively"""

        limits_dict = {0:'',1:':MAX',-1:':MIN'}
        command = ctypes.c_char_p((':FREQ'+limits_dict[limits]+'?').encode())

        rx = self.dll.usbCommWrite(self.serialnum,command)

        freq_string = rx.decode()
        assert(freq_string!='Invalid Command')
        [value,suffix] = freq_string.strip().split()

        try:
            freq = float(value)*self.suffix_dict[suffix]
        except KeyError as e:
            raise Exception('Invalid suffix "' + e.args[0] + '"')
        return freq

    def set_freq(self,freq):
        """Sets the output frequency of the Holzworth synth"""

        if (freq<1e5) or (freq>2.048e9):
            raise Exception("Frequency out of range")

        exponent = 3.0*np.floor(np.log10(freq)/3.0) #find nearest SI suffix exponent (i.e. 1,3,6 or 9)
        multiplier = np.power(10,exponent)

        try:
            freq_string = str(freq/multiplier) + self.multiplier_dict[multiplier]
        except KeyError as e:
            raise Exception('Invalid suffix "' + e.args[0] + '"')

        command = ctypes.c_char_p((':FREQ:'+freq_string).encode())
        rx = self.dll.usbCommWrite(self.serialnum,command)
        assert(rx.decode()!='Invalid Command')

        if rx.decode() != 'Frequency Set':
            assert(self.get_freq() == freq)

    def identity(self):
        command = ctypes.c_char_p((':IDN?').encode())
        rx = self.dll.usbCommWrite(self.serialnum,command)
        return rx.decode()

    def ping(self):
        if self.identity() == '':
            raise Exception("No devices connected")
        
        return True

    def close(self):
        """Closes connection to the Holzworth. Must be called when disconnecting else future connections may not work"""

        self.dll.close_all()
        print('Connection to Holzworth synth closed safely')
