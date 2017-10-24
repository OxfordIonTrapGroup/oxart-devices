from artiq.language.core import *
from .driver_raw import HolzworthSynthRaw
import math
import json
import datetime
import dateutil.parser as parser
import asyncio
import os

class HolzworthSynth():
    """Driver for Holzworth synth to get and set the frequency, and get and set the ramp rate to track the 674 nm quadrupole laser cavity drift."""

    def __init__(self):

        self.synth_raw = HolzworthSynthRaw() #The raw driver
        self.max_step = 10e3 # Hz
        folder = os.path.dirname(os.path.realpath(__file__)) #Saves the log file in the same folder as the driver, so it can be backed up with git
        file_name = "Holzworth_freq_log.txt"
        self.logfile_path = os.path.join(folder,file_name)
        if not os.path.isfile(self.logfile_path):
            raise Exception("No log file found")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.continuously_update_freq(loop)) # Starts continuously_update_freq

    async def continuously_update_freq(self,loop):
        """Updates the frequency every 10 seconds and adds itself back to the lop"""
        await self.update_freq()
        await asyncio.sleep(10)
        asyncio.ensure_future(self.continuously_update_freq(loop),loop = loop)


    async def _move_freq(self, freq):
        """ Slowly scans synth in small steps to requested frequency to keep lock"""
        freq_start = self.synth_raw.get_freq()
        freq_end  = freq
        n_steps = math.ceil(abs(freq_end-freq_start)/self.max_step)
        for n in range(1,n_steps+1):
            f = freq_start + (n/n_steps)*(freq_end-freq_start)

            self.synth_raw.set_freq(f)
            await asyncio.sleep(0)

        assert(math.isclose(await self.get_freq(),freq_end,rel_tol=0.5e-12,abs_tol=0.0011)) #Checking we reach the final frequency, allowing for rounding differences in the 3rd decimal place for values as large as 2.048 GHZ (max frequency output)


    async def set_freq(self, freq):
        """Sets the Holzworth frequency and saves the value and datetime to file."""
        with open(self.logfile_path,"r+") as f: # Reads file only
            try:                               # try block to catch when logfile is empty
                data = json.load(f)
            except ValueError:
                data = {}

        await self._move_freq(freq)

        data["date_freq_set"] = datetime.datetime.now().isoformat()
        data["last_freq_set"] = freq

        with open(self.logfile_path,"w") as f: # Overwrites files       
            json.dump(data,f)

        
    async def get_freq(self):
        """Gets the current frequency of the synth"""
        return self.synth_raw.get_freq()



    async def update_freq(self):
        """Updates the frequency by the difference between the current time and the last time set_freq was called multiplied by the drift rate."""
        with open(self.logfile_path,"r") as f:
            try:
                data = json.load(f)
            except ValueError:
                raise Exception("Empty log file")

        ramp = data["ramp"] #Hz per second
        ref_freq = data["last_freq_set"] #Freq when it was last set (not updated)
        duration  = datetime.datetime.now() - parser.parse(data["date_freq_set"])
        new_freq = duration.total_seconds()*ramp + ref_freq

        await self._move_freq(new_freq)

        data["date_freq_updated"] = datetime.datetime.now().isoformat()
        #print("Frequency updated to {} Hz".format(self.get_freq()))

        with open(self.logfile_path,"w") as f: # Overwrites files       
            json.dump(data,f)

    def get_ramp(self):
        """Retrives the ramp rate from the log file"""
        with open(self.logfile_path,"r") as f:
            try:
                data = json.load(f)
            except ValueError:
                raise Exception("Empty log file")

        return data["ramp"]

    def set_ramp(self,ramp):
        """Sets the ramp rate the ramp rate from the log file"""
        with open(self.logfile_path,"r") as f:
            try:                                     # try block to catch when logfile is empty
                data = json.load(f)
            except ValueError:
                data = {}

        data["ramp"] = ramp #Hz per second
        data["date_ramp_modified"] = datetime.datetime.now().isoformat()

        with open(self.logfile_path,"w") as f: # Overwrites files       
            json.dump(data,f)

    async def ping(self):
        """Master needs to be able to ping the device"""
        return self.synth_raw.ping()

    def close(self):
        self.synth_raw.close()

    async def terminate(self):
        """If something goes wrong the master calls this function"""
        self.close()
        



