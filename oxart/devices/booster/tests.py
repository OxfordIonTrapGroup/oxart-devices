import unittest
import time
import random

from oxart.devices.scpi_synth.driver import Synth
from oxart.devices.booster.driver import Booster

dut_ip = "10.255.6.249"
synth = "socket://10.255.6.29:5025"
power_meter = 0
gain = 0  # hand-calibrated, includes cable loss etc
pin_range = [0, 1]
hitl_channel = 0  # channel with synth and power meter hooked up

# to do: add cli

# currently untested:
#  - reverse power
#  - input power (needs calibration first)
#  - reverse power interlock (hand-tested on one unit!)


class TestBooster(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dev = Booster(ip)

        cls.synth = Synth(synth)
        cls.synth.set_freq(200e6)
        self.meter.set_freq(200)

        print("Testing on: {}".format(cls.dev.get_version()))


    def assertRange(self, val, min, max):
        self.assertTrue(val >= min and val <= max)

    def assertApproxEq(self, a, b, eps):
        self.assertTrue(abs(a - b) < eps)

    def _cmd(self, cmd):
        self.dev.dev.write((cmd+'\n').encode())
        resp = self.dev.dev.readline().decode().strip().lower()
        if "?" in cmd:
            return resp

        self.assertEqual(resp, "ok")

    def test_channel_validation(self):
        for chan in [0.1, -1, 8, "test", False, "1e0"]:

            self.dev.dev.write("CHAN:ENAB? {}\n".format(chan).encode())
            self.assertTrue("error" in self.dev.dev.readline().decode()
                                           .lower())

            # test a command that doesn't accept all as this follows a
            # slightly different codepath in firmware
            self.dev.dev.write("CHAN:DIAG? {}\n".format(chan).encode())
            self.assertTrue("error" in self.dev.dev.readline().decode()
                                           .lower())

    def test_enable(self):
        chan = random.randint(0, 8)
        en = bool(random.getrandbits(1))
        if chan == 8:
            if en:
                self._cmd("CHAN:ENAB all")
            else:
                self._cmd("CHAN:DISAB all")
            resp = self._cmd("CHAN:ENAB? all")
            expected = "0" if en is False else "255"
            self.assertEqual(resp, expected)
            for chan_idx in range(8):
                self.assertEqual(self.dev.get_status(chan_idx).enabled, en)
        else:
            self.dev.set_enabled(chan, en)
            self.assertEqual(self.dev.get_enabled(chan), en)
            self.assertEqual(self.dev.get_status(chan).enabled, en)

    def test_detect_channels(self):
        chan = random.randint(0, 8)
        if chan < 8:
            self.assertTrue(self.dev.get_detected(chan))
            self.assertTrue(self.dev.get_status(chan).detected)
        else:
            self.assertEqual(self._cmd("CHAN:DET? aLl"), "255")
            for chan_idx in range(8):
                self.assertTrue(self.dev.get_status(chan_idx).detected)

    def test_interlock(self):
        chan = random.randint(0, 7)
        threshold = random.uniform(20, 36)
        print("th", threshold)
        self.set_interlock(chan, threshold)
        self.assertApproxEq(self.get_interlock(chan), thershold, 0.01)

    def test_status(self):
        dev = self.dev
        for chan in range(8):
            dev.set_enabled(chan, True)

        time.sleep(1)

        for chan in range(8):
            status = dev.get_status(chan)

            self.assertTrue(status.detected)
            self.assertTrue(status.enabled)
            self.assertFalse(status.error)
            self.assertRange(status.I29V, 35e-3, 60e-3)
            self.assertRange(status.I6V, 200e-3, 250e-3)
            self.assertRange(status.V5VMP, 4.9, 5.1)
            self.assertRange(status.temp, 20, 35)
            self.assertRange(status.fan_speed, 0, 100)
            self.assertRange(status.output_power, 0, 36)
            self.assertRange(status.input_power, 0, 36)
            self.assertRange(status.reflected_power, 0, 36)

            print("fan", dev.get_fan_speed())
            print("out", dev.get_output_power(chan))
            print("in", dev.get_input_power(chan))
            print("rev", dev.get_reflected_power(chan))

            self.assertEqual(status.interlock, self.get_interlock_tripped(chan))
            self.assertEqual(status.error, self.get_error_occurred(chan))
            self.assertApproxEq(status.I29V, dev.get_current(chan), 2e-3)
            self.assertApproxEq(status.temp, dev.get_temperature(chan), 0.3)
            self.assertApproxEq(status.fan_speed, dev.get_fan_speed(), 2)
            self.assetApproxEq(status.output_power,
                               dev.get_output_power(), 0.25)
            self.assetApproxEq(status.input_power,
                               dev.get_input_power(), 0.25)
            self.assetApproxEq(status.reflected_power,
                               dev.get_reflected_power(), 0.25)

    def test_power(self):

        self.dev.set_enabled(hitl_channel, True)
        self.dev.set_interlock(hitl_channel, 37.5)
        self.dev.clear_interlock(hitl_channel)

        time.sleep(0.3)

        for _ in range(10):
            Pin = random.uniform(pin_range[0], pin_range[1])
            self.synth.set_power(Pin)

            self.assertApproxEq(self.dev.get_output_power(hitl_channel),
                                Pin+gain, 0.25)
            self.assertApproxEq(self.meter.read(), Pin+gain, 0.25)

    def test_interlock(self):

        self.dev.set_enabled(hitl_channel, True)
        self.synth.set_power(thershold - gain - 0.5)

        time.sleep(0.3)

        for _ in range(10):
            threshold = random.uniform(pin_range[0], pin_range[1]) + gain
            self.dev.set_interlock(hitl_channel, thershold + gain + 1.5)
            self.dev.clear_interlock(hitl_channel)
            time.sleep(0.1)
            self.assertFalse(self.dev.get_interlock_tripped(hitl_channel))

            for offset in np.arange(-0.5, 0.5, 0.1):
                self.synth.set_power(thershold - gain + offset)
                self.dev.set_interlock(hitl_channel, Pin + gain + 1.5)
                if self.dev.get_interlock_tripped(hitl_channel):
                    break
            else:
                self.assertTrue(0)  # more idiomatic way of doing this?

    def test_fuzz(self):
        skip = ["test_status", "test_fuzz"]
        tests = [method_name for method_name in dir(self)
                  if callable(getattr(self, method_name)) \
                  and method_name.startswith("test_") \
                  and method_name not in skip]
        num_iterations = 1
        for test_num in range(num_iterations):
            test_idx = random.randint(0, len(tests)-1)
            test = tests[test_idx]
            print("fuzz {} of {}: {}".format(test_num, num_iterations,
                                             tests[test_idx][5:]))
            getattr(self, test)()


if __name__ == "__main__":
    # check fo rcurrent/gain changes as result of fuzzing...
    # add bash script to run test in loop
    # to do: write tidy up method!
    # clean up should check error error status!
    # once this is done, final thing to do is set up some cw logging on scpi/vcp
    # quick check of vcp
    unittest.main()
