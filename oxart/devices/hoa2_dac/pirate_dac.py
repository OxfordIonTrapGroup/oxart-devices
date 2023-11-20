# Require pyBusPirateLite
# https://github.com/juhasch/pyBusPirateLite.git
#
# NB as of 11/11/2019, the above requires python 3.6, use
# commit 50b1177d426d1741fa29b361f07e2f6d77848f78 for 3.5

import time
from pyBusPirateLite.SPI import *


# CS : SYNC_N
# AUX : LDAC
class PirateDac:

    def __init__(self, port):
        self.spi = SPI(portname=port)
        self.spi.pins = PIN_POWER | PIN_AUX
        self.spi.config = CFG_PUSH_PULL
        self.spi.speed = '1MHz'
        self.spi.cs = False

        # Config +-10V range, power up
        self._write(0x1f, reg=2, ch=0)
        self._write(0x4, reg=1, ch=4)

    def pulse_ldac(self):
        self.spi.pins = PIN_POWER | PIN_CS
        time.sleep(0.1e-3)
        self.spi.pins = PIN_POWER | PIN_CS | PIN_AUX

    def _write(self, data, reg=0, ch=0, rw=0):
        """Read/write a 16 bit data word to a given register and channel
        reg : 0 -> DAC, 1 -> output range, 2 -> power control, 3 -> control
        rw : 0 -> write, 1 -> read
        ch : 0-3 for ch 0-3, 4 -> all
        """
        ctrl = (rw << 7) + ((reg & 0x7) << 3) + (ch & 0x7)
        self.spi.write_then_read(3, 0, [ctrl, (data >> 8) & 0xff, data & 0xff])

    def _read(self):
        self.spi.cs = True
        return self.spi.transfer([0x18, 0x0, 0x0])
        self.spi.cs = False

    def read_channel(self, ch=0):
        self._write(0, reg=0, ch=ch, rw=1)
        raw = self._read()
        val_lsb = int.from_bytes(raw[1:], byteorder='big')
        val = val_lsb * (10 / 32767)
        return val

    def set_channel(self, v, ch=0, update=True):
        """Set channel to a given voltage.
        If update, pulse LDAC and update immediately,
        else batch and update together on LDAC"""

        if v > 10 or v < -10:
            raise ValueError("Voltage out of range")

        raw = int(v / 10 * 32767)
        if raw < 0:
            raw += 2**16
        self._write(raw, ch=ch)

        if update:
            self.pulse_ldac()


if __name__ == "__main__":
    print("Opening ...")
    dac = PirateDac('com14')

    print("Sweeping DACs")

    def write(v):
        for ch in range(4):
            dac.set_channel(v, ch=ch, update=False)
        dac.pulse_ldac()

    i = 0
    while True:
        i += 1
        if i > 10:
            i = -10
        write(i)
