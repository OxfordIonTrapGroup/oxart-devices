from oxart.devices.scpi_device.driver import SCPIDevice
import numpy as np
import os


def numtostr(mystr):
    return '%20.15e' % mystr


class RS_ZVL:

    def __init__(self, device='10.255.6.21'):
        self.ip = device
        # self.stream = get_stream(device)
        self.dev = SCPIDevice(device)

    def close(self):
        self.dev.close()

    def ping(self):
        return True  # hot fix as ping is requested during scans...
        mystr = 'SYST:VERS?'  # should always be "1997.0"
        pp = self.dev.query(mystr)
        return pp == "1997.0"

    def Reset(self):
        # self.dev.send("*RST")
        pass

    def SetIFBW(self, x):
        self.dev.send('BAND ' + numtostr(x))

    def SetContinuous(self, on):
        if on:
            self.dev.send('INIT:CONT ON')
        elif not on:
            self.dev.send('INIT:CONT OFF')

    def SetRange(self, start, end):
        self.SetStart(start)
        self.SetEnd(end)

    def SetCenterSpan(self, center, span):
        self.SetCenter(center)
        self.SetSpan(span)

    def GetAllData(self, keep_uncal=True):
        pars, parnames = self.GetTraceNames()
        self.SetActiveTrace(pars[0])
        names = ['Frequency (Hz)']
        alltrc = [self.GetFrequency()]
        for pp in parnames:
            names.append('%sre ()' % pp)
            names.append('%sim ()' % pp)
            names.append('%sdB (dB)' % pp)
            names.append('%sPh (rad)' % pp)
        for par in pars:
            self.SetActiveTrace(par)
            yyre, yyim = self.GetTraceData()
            alltrc.append(yyre)
            alltrc.append(yyim)
            yydb = 20. * np.log10(np.abs(yyre + 1j * yyim))
            yyph = np.unwrap(np.angle(yyre + 1j * yyim))
            alltrc.append(yydb)
            alltrc.append(yyph)
        Cal = self.GetCal()
        if Cal and keep_uncal:
            for pp in parnames:
                names.append('%sre unc ()' % pp)
                names.append('%sim unc ()' % pp)
                names.append('%sdB unc (dB)' % pp)
                names.append('%sPh unc (rad)' % pp)
            self.CalOff()
            for par in pars:
                self.SetActiveTrace(par)
                yyre, yyim = self.GetTraceData()
                alltrc.append(yyre)
                alltrc.append(yyim)
                yydb = 20. * np.log10(np.abs(yyre + 1j * yyim))
                yyph = np.unwrap(np.angle(yyre + 1j * yyim))
                alltrc.append(yydb)
                alltrc.append(yyph)
            self.CalOn()
        final = {}
        for name, data in zip(names, alltrc):
            final[name] = data
        return final

    def MeasureScreen(self, keep_uncal=True, N_averages=1):
        self.SetContinuous(False)
        if N_averages == 1:
            self.Trigger()  #Trigger single sweep and wait for response
            return self.GetAllData(keep_uncal)
        elif N_averages > 1:
            self.dev.send('SENS:AVER:COUN %d' % N_averages)
            self.dev.send('SENS:AVER ON')
            self.dev.send('SENS:AVER:CLEAR')
            naver = int(self.dev.query('SENS:AVER:COUN?'))
            for _ in range(naver):
                self.Trigger()
            dat = self.GetAllData(keep_uncal)
            # self.AutoScaleAll()
            self.dev.send('SENS:AVER OFF')
            return dat

    def SetStart(self, x):
        mystr = numtostr(x)
        mystr = 'SENS:FREQ:STAR ' + mystr
        self.dev.send(mystr)

    def SetEnd(self, x):
        mystr = numtostr(x)
        mystr = 'SENS:FREQ:STOP ' + mystr
        self.dev.send(mystr)

    def SetCenter(self, x):
        mystr = numtostr(x)
        mystr = 'SENS:FREQ:CENT ' + mystr
        self.dev.send(mystr)

    def SetSpan(self, x):
        mystr = numtostr(x)
        mystr = 'SENS:FREQ:SPAN ' + mystr
        self.dev.send(mystr)

    def GetStart(self):
        mystr = 'SENS:FREQ:STAR?'
        pp = self.dev.query(mystr)
        pp = float(pp)
        return pp

    def GetEnd(self):
        mystr = 'SENS:FREQ:STOP?'
        pp = self.dev.query(mystr)
        pp = float(pp)
        return pp

    def GetCenter(self):
        mystr = 'SENS:FREQ:CENT?'
        pp = self.dev.query(mystr)
        pp = float(pp)
        return pp

    def GetSpan(self):
        mystr = 'SENS:FREQ:SPAN?'
        pp = self.dev.query(mystr)
        pp = float(pp)
        return pp

    def SetIFBW(self, x):
        mystr = numtostr(x)
        mystr = 'SENS:BWID ' + mystr
        self.dev.send(mystr)

    def GetIFBW(self):
        mystr = 'SENS:BWID?'
        pp = self.dev.query(mystr)
        pp = float(pp)
        return pp

    def SetPower(self, x):
        assert x <= 0
        mystr = numtostr(x)
        mystr = 'SOUR:POW ' + mystr
        self.dev.send(mystr)

    def GetPower(self):
        mystr = 'SOUR:POW?'
        pp = self.dev.query(mystr)
        pp = float(pp)
        return pp

    def SetPoints(self, x):
        mystr = '%d' % x
        mystr = 'SENS:SWE:POIN ' + mystr
        self.dev.send(mystr)

    def GetPoints(self):
        mystr = 'SENS:SWE:POIN?'
        pp = self.dev.query(mystr)
        pp = int(pp)
        return pp

    def Trigger(self, block=True):
        if block:
            (self.dev.query('INIT;*OPC?'))
        else:
            self.dev.send('INIT')
        return

    def SetPowerOff(self):
        self.dev.send("SOUR1:POW1:MODE OFF")
        return

    def SetPowerOn(self):
        self.dev.send("SOUR1:POW1:MODE ON")
        return

    def SetAverageCounts(self, x):
        self.dev.send('SENS:AVER:COUN {}'.format(2000))
        return

    def SetAverageOn(self):
        self.dev.send('SENS:AVER ON')
        return

    def SetAverageOff(self):
        self.dev.send('SENS:AVER OFF')
        return

    def GetFrequency(self):
        freq = self.dev.query('CALC:DATA:STIM?')
        freq = np.asarray([float(xx) for xx in freq.split(',')])
        return freq

    def GetTraceNames(self):
        pars = self.dev.query('CALC:PAR:CAT?')
        pars = pars.strip('\n').strip("'").split(',')
        parnames = pars[1::2]
        pars = pars[::2]
        return pars, parnames

    def SetActiveTrace(self, mystr):
        self.dev.send('CALC:PAR:SEL "%s"' % mystr)

    def GetTraceData(self):
        yy = self.dev.query("CALC:DATA? SDATA")
        yy = np.asarray([float(xx) for xx in yy.split(',')])
        yyre = yy[::2]
        yyim = yy[1::2]
        return yyre, yyim

    def CalOn(self):
        mystr = "CORR ON"
        self.dev.send(mystr)

    def CalOff(self):
        mystr = "CORR OFF"
        self.dev.send(mystr)

    def GetCal(self):
        return bool(int(self.dev.query('CORR?')))

    def SetupS11(self):
        self.Reset()
        self.SetContinuous(False)  #Turn off continuous mode
        self.write('CALC:PAR:DEL:ALL')  #Delete default trace
        tracenames = ['\'TrS11\'']
        tracevars = ['\'S11\'']
        for name, var in zip(tracenames, tracevars):
            self.write('CALC:PAR:SDEF ' + name + ', ' + var)
            self.write('DISP:WIND1:TRAC:EFE ' + name)

    def SetupS21(self):
        self.Reset()
        self.SetContinuous(False)  #Turn off continuous mode
        self.write('CALC:PAR:DEL:ALL')  #Delete default trace
        tracenames = ['\'TrS21\'']
        tracevars = ['\'S21\'']
        for name, var in zip(tracenames, tracevars):
            self.write('CALC:PAR:SDEF ' + name + ', ' +
                       var)  #Set 2 traces and measurements
            self.write('DISP:WIND1:TRAC:EFE ' + name)

    def write(self, x):
        self.dev.send(x)

    def query(self, x):
        return self.dev.query(x)

    def SetReference(self, ref='EXT'):
        # INT, EXT, ELO
        self.write('ROSC:SOUR ' + ref)
        return self.dev.query('ROSC:SOUR?')

    #####

    def acquire_S11(self, start, stop, points, ifbw=1e3, power=-20, N_averages=1):
        self.SetupS11()
        self.SetRange(start, stop)
        self.SetIFBW(ifbw)
        self.SetPower(power)
        self.SetPoints(points)
        data = self.MeasureScreen(keep_uncal=False, N_averages=N_averages)
        return data

    def acquire_S21(self, start, stop, points, ifbw=1e3, power=-20, N_averages=1):
        self.SetupS21()
        self.SetRange(start, stop)
        self.SetIFBW(ifbw)
        self.SetPower(power)
        self.SetPoints(points)
        data = self.MeasureScreen(keep_uncal=False, N_averages=N_averages)
        return data


if __name__ == "__main__":
    vna = RS_ZVL()
    data = vna.MeasureScreen(keep_uncal=False)
    print(data)
