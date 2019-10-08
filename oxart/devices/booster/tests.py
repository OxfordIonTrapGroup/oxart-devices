import argparse
import unittest
import time
import random
import sys

from artiq.protocols.pc_rpc import Client

from oxart.devices.scpi_synth.driver import Synth
from oxart.devices.booster.driver import Booster

parser = argparse.ArgumentParser(description="Booster hardware in the loop "
                                 "test suite. Connect one channel of Booster "
                                 "to a synth and RF power meter.")
parser.add_argument("--read_only",
                    help="If set, no tests are run which would change the sate"
                    " of any hardware. This mode allows testing multiple SCPI "
                    "connections simultaneously.")
parser.add_argument("--booster", help="IP address of the Booster to test")
parser.add_argument("--synth", help="Address of the synth to use for tests")
parser.add_argument("--meter", help="IP address of the power meter RPC server")
parser.add_argument("--p_min",
                    help="Minimum synth power to use, set to give ~25dBm "
                    "output power",
                    type=float)
parser.add_argument("--p_max",
                    help="Maximum synth power to use, set to give ~35dBm "
                    "output power",
                    type=float)
parser.add_argument("--chan",
                    help="Booster channel connected to synth + power meter",
                    type=int)
args = None


class TestBooster(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dev = Booster(args.booster)

        cls.synth = Synth(args.synth)
        cls.synth.set_freq(200e6)
        cls.synth.set_rf_on(False)

        cls.meter = Client(args.meter, 4300)
        cls.meter.set_freq(200)

        cls.I29V = [0.]*8
        cls.I6V = [0.]*8
        #  the noise I measure is about +-2.1mA, so this gives a little slack
        #  for infrequent glitches that aren't out of the realm of the ordinary
        cls.I_tol = 4.5e-3  # expect currents to be stable to +- this level
        cls.t_settle = 4  # delay between enabling channels and taking data...

        for channel in range(8):
            if channel == 3:
                continue
            cls.dev.set_enabled(channel)

        time.sleep(cls.t_settle)

        for channel in range(8):
            if channel == 3:
                continue

            status = cls.dev.get_status(channel)
            cls.I29V[channel] = status.I29V
            cls.I6V[channel] = status.I6V

        print("Testing on: {}".format(cls.dev.get_version()))
        print("29V currents: {}".format(cls.I29V))
        print("6V currents: {}".format(cls.I6V))

        cls.dev.set_interlock(args.chan, 37)
        cls.synth.set_power(args.p_min)
        cls.synth.set_rf_on(True)
        time.sleep(0.3)
        cls.gain_max = cls.meter.read() - args.p_min + 30  # 30dB attenuator
        cls.detector_err_min = (cls.dev.get_output_power(args.chan) -
                                cls.meter.read() - 30)

        cls.synth.set_power(args.p_max)
        time.sleep(0.2)
        cls.gain_min = cls.meter.read() - args.p_max + 30  # 30dB attenuator

        cls.detector_err_max = (cls.dev.get_output_power(args.chan) -
                                cls.meter.read() - 30)

        cls.gain = 0.5*(cls.gain_min+cls.gain_max)
        cls.detector_err = 0.5*(cls.detector_err_max + cls.detector_err_min)
        print("Amp gain: {} dB (min {} dB, max {} dB".format(cls.gain,
                                                             cls.gain_min,
                                                             cls.gain_max))
        print("Detector error: {} dB ({} db - {} dB)".format(
            cls.detector_err, cls.detector_err_min, cls.detector_err_max))

        cls.synth.set_rf_on(False)
        time.sleep(cls.t_settle)

    def assertRange(self, val, min, max):
        if not(val >= min and val <= max):
            print("fail!", val, min, max)
        self.assertTrue(val >= min and val <= max)

    def assertApproxEq(self, a, b, eps):
        if not(abs(a - b) < eps):
            print("fail!", a, b, eps)
        self.assertTrue(abs(a - b) < eps)

    def _cmd(self, cmd):
        self.dev.dev.write((cmd+'\n').encode())
        resp = self.dev.dev.readline().decode().strip().lower()
        if "?" in cmd:
            return resp
        self.assertEqual(resp, "ok")

    def check_errors(func):
        def wrapped(self, *args, **kwargs):
            func(self, *args, **kwargs)
            for chan in range(8):
                if chan == 3:
                    continue
                status = self.dev.get_status(chan)
                self.assertTrue(status.i2c_error_count == 0)
                self.assertFalse(status.error_occurred)
                if status.enabled:
                    self.assertApproxEq(status.I6V, self.I6V[chan], 6e-3)
                    self.assertApproxEq(status.I29V, self.I29V[chan],
                                        self.I_tol)
                self.assertRange(status.temp, 20, 35)

        return wrapped

    @check_errors
    def test_channel_validation(self):
        for chan in [0.1, -1, 8, "test", False, "1e0"]:

            self.dev.dev.write("CHAN:ENAB? {}\n".format(chan).encode())
            self.assertTrue("error" in self.dev.dev.readline().decode()
                                           .lower())

            # test a command that doesn't accept all as this follows a
            # slightly different code path in firmware
            self.dev.dev.write("CHAN:DIAG? {}\n".format(chan).encode())
            self.assertTrue("error" in self.dev.dev.readline().decode()
                                           .lower())

    @check_errors
    def test_enable(self):
        chan = random.randint(0, 8)
        en = bool(random.getrandbits(1))
        print("test enable: channel={}, enabled={}".format(chan, en))
        if chan == 8:
            return  # broken channel
            if en:
                self._cmd("CHAN:ENAB all")
            else:
                self._cmd("CHAN:DISAB all")
            resp = self._cmd("CHAN:ENAB? all")
            expected = "0" if en is False else "255"
            self.assertEqual(resp, expected)

            for chan_idx in range(8):
                if chan == 3:
                    continue
                self.assertEqual(self.dev.get_status(chan_idx).enabled, en)
        else:
            if chan == 3:
                return
            self.dev.set_enabled(chan, en)
            self.assertEqual(self.dev.get_enabled(chan), en)
            self.assertEqual(self.dev.get_status(chan).enabled, en)

        time.sleep(self.t_settle)  # let things stabilize

    @check_errors
    def test_detect_channels(self):
        chan = random.randint(0, 8)
        if chan < 8:
            if chan == 3:
                return
            self.assertTrue(self.dev.get_detected(chan))
            self.assertTrue(self.dev.get_status(chan).detected)
        else:
            self.assertEqual(self._cmd("CHAN:DET? aLl"), "255")
            for chan_idx in range(8):
                if chan_idx == 3:
                    continue
                self.assertTrue(self.dev.get_status(chan_idx).detected)

    @check_errors
    def test_status(self):
        dev = self.dev

        for chan in range(8):
            if chan == 3:
                continue
            status = dev.get_status(chan)

            self.assertTrue(status.detected)
            self.assertFalse(status.error_occurred)
            self.assertRange(status.temp, 20, 35)
            self.assertRange(status.fan_speed, 0, 100)
            self.assertRange(status.output_power, 0, 36)
            # self.assertRange(status.input_power, 0, 36)
            self.assertRange(status.reflected_power, -20, 36)

            self.assertEqual(status.detected, dev.get_detected(chan))
            self.assertEqual(status.enabled, dev.get_enabled(chan))
            self.assertEqual(status.interlock, dev.get_interlock_tripped(chan))
            self.assertEqual(status.error_occurred,
                             dev.get_error_occurred(chan))
            self.assertApproxEq(status.temp, dev.get_temperature(chan), 2)
            self.assertApproxEq(status.fan_speed, dev.get_fan_speed(), 2)
            self.assertApproxEq(status.output_power,
                                dev.get_output_power(chan), 0.25)
            # self.assertApproxEq(status.input_power,
            #                    dev.get_input_power(), 0.25)
            self.assertApproxEq(status.reflected_power,
                                dev.get_reflected_power(chan), 0.25)

            if status.enabled:
                self.assertRange(status.V5VMP, 4.9, 5.1)
                self.assertRange(status.I29V, 25e-3, 60e-3)
                self.assertRange(status.I6V, 200e-3, 280e-3)
                self.assertApproxEq(status.I29V, dev.get_current(chan),
                                    self.I_tol)

    @check_errors
    def test_interlock(self):

        self.synth.set_rf_on(True)
        for idx in range(10):
            P_synth = random.uniform(args.p_min, args.p_max)
            offset = -1.5

            self.dev.set_enabled(args.chan, True)
            self.dev.set_interlock(args.chan, P_synth+self.gain)

            self.synth.set_power(P_synth+offset)
            time.sleep(0.2)
            self.dev.clear_interlock(args.chan)
            time.sleep(0.1)

            while not self.dev.get_interlock_tripped(args.chan):
                offset += 0.1
                self.synth.set_power(P_synth+offset)
                time.sleep(0.2)
                if offset > 1.5:
                    break

            print(offset)
            self.assertTrue(abs(offset) < 1.5)
        self.synth.set_rf_on(False)
        time.sleep(0.1)
        self.dev.clear_interlock(args.chan)
        time.sleep(self.t_settle)

    @check_errors
    def test_power(self):

        for idx in range(10):
            P_synth = random.uniform(args.p_min, args.p_max)

            self.dev.set_enabled(args.chan, True)
            self.dev.set_interlock(args.chan, 37.5)
            self.dev.clear_interlock(args.chan)
            self.synth.set_power(P_synth)
            self.synth.set_rf_on(True)

            time.sleep(0.5)

            P_meter = self.meter.read() + 30
            P_booster = self.dev.get_output_power(args.chan)
            gain = P_booster - P_synth
            detector_err = P_booster - P_meter

            self.assertApproxEq(gain, self.gain, 1.0)  # 1dB is non-linearity
            self.assertApproxEq(detector_err, 0, 0.3)

        self.synth.set_rf_on(False)
        time.sleep(0.1)
        self.dev.clear_interlock(args.chan)
        time.sleep(self.t_settle)

    def test_fuzz(self):
        skip = ["test_fuzz"]
        tests = [method_name for method_name in dir(self) if (
            callable(getattr(self, method_name))
            and method_name.startswith("test_")
            and method_name not in skip)]
        num_iterations = 10000
        for test_num in range(num_iterations):
            test_idx = random.randint(0, len(tests)-1)
            test = tests[test_idx]
            print("fuzz {} of {}: {}".format(test_num, num_iterations,
                                             tests[test_idx][5:]))
            getattr(self, test)()


if __name__ == "__main__":
    # fuzz with both invasive and non-invasive at same time
    # to do: skim read and push
    args = parser.parse_args()
    print(sys.argv[0])
    unittest.main(argv=sys.argv[0:1])
