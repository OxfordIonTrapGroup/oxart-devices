from gm0 import *
import time 

units = {"Gauss":1,"Tesla":0,"A/m":2,"Oe":3}
modes = {"DC":0,"DC Peak":1,"AC":2,"AC Max":3,"AC Peak":4,"Hold":5}

class GaussMeter:

    def __init__(self, device):
        self.handle = gm0_newgm(device,0)
        gm0_startconnect(self.handle)

        #Gm08 is slow at connecting. 
        while gm0_getconnect(self.handle) == 0:
            time.sleep(1)

        assert self.ping()

        self.default()

    def identify(self):
        self.stream.write("*IDN?\n".encode())
        return self.stream.readline().decode()

    def get_unit(self):
        unit = gm0_getunits(self.handle)
        return units[unit]

    def set_unit(self,unit_str):
        if unit_str in units.keys():
            gm0_setunits(self.handle,units[unit_str])
            time.sleep(1)
        else:
            raise ValueError(unit_str+" is not an accepted unit")
   
    def get_mode(self):
        mode = gm0_getmode(self.handle)
        return modes[mode]
   
    def set_mode(self,mode_str):
        if mode_str in modes.keys():
            gm0_setmode(self.handle,modes[mode_str])
            time.sleep(1)
        else:
            raise ValueError(mode_str+" is not an accepted mode")
    
    def null_ranges(self):
        for x in range(4):
            gm0_setrange(self.handle,x) 
            time.sleep(1)
            gm0_donull(self.handle)
            time.sleep(1)
            gm0_resetnull(self.handle)
            time.sleep(1)

    def set_range(self,rng):
        gm0_setrange(self.handle,rng)
    
    def autorange(self):
        self.set_range(4)

    def measure(self):
        val = gm0_getvalue(self.handle)
        return val

    def ping(self):
        '''
        perform a ping by querying the connected status
        1 = connected
        0 = connecting
        <0 = error
        ''' 
        p = gm0_getconnect(self.handle)
        return p == 1
    
    def get_serial_no(self):
        #return a tuple of probe serial no and meter serial no.
        return (gm0_getprobesn(self.handle),gm0_getmetersn(self.handle))

    def default(self):
        self.set_unit("Gauss")
        self.set_mode("DC")
        self.autorange

    def close(self):
        exit()

if __name__ == "__main__":
    gmtest = GaussMeter(-1)
    try:
        for i in range(10):
            print(gmtest.ping())
            time.sleep(1)
            print(gmtest.measure())
            time.sleep(1)
    except:
        gmtest.close()
    finally:
        gmtest.close()