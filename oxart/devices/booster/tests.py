import numpy as np
import argparse
import unittest
import time
import random
import sys

from sipyco.pc_rpc import Client

from oxart.devices.scpi_synth.driver import Synth
from oxart.devices.booster.driver import Booster

parser = argparse.ArgumentParser(description="Booster hardware in the loop "
                                 "test suite. Connect one channel of Booster "
                                 "to a synth and RF power meter. Assumes there"
                                 " is a 30dB attenuator between Booster and "
                                 "the power meter.")
parser.add_argument("--booster", help="IP address of the Booster to test")
parser.add_argument("--synth", help="Address of the synth to use for tests")
parser.add_argument("--meter", help="IP address of the power meter RPC server")
parser.add_argument(
    "--p_min",
    help="Minimum synth power to use, set to give ~25dBm "
    "output power",
    type=float,
)
parser.add_argument(
    "--p_max",
    help="Maximum synth power to use, set to give ~35dBm "
    "output power",
    type=float,
)
parser.add_argument(
    "--chan",
    help="Booster channel connected to synth + power meter",
    type=int,
    default=0,
)
args = None

# python -m oxart.devices.booster.tests --booster "10.255.6.79" --synth
# "socket://10.255.6.123:5025" --meter "10.255.6.125" --p_min -15.00 --p_max
# -5.00


class TestBooster(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dev = Booster(args.booster)
        print("Testing Booster: {}".format(cls.dev.get_version()))

        # level of stability we expect for the current measurements
        # we allow a wider margin for the channel under test (cut) because
        # of thermal hysteresis (as it gets hotter, the bias current decreases
        # a little)
        cls.I29V_tol = 3.5e-3
        cls.I29V_cut_tol = 3.5e-3
        cls.I6V_tol = 2e-3
        cls.I6V_cut_tol = 3e-3

        cls.t_settle = 4  # delay (s) between enabling channels and taking data

        for channel in range(8):
            cls.dev.set_enabled(channel)

        cls.cut = args.chan
        cls.synth = Synth(args.synth)
        cls.synth.set_freq(200e6)
        cls.synth.set_rf_on(False)

        cls.meter = Client(args.meter, 4300)
        cls.meter.set_freq(200)

        time.sleep(cls.t_settle)

        # get a baseline measurement of the currents on each channel
        num_measurements = 100
        cls.I29V = np.zeros((8, num_measurements))
        cls.I6V = np.zeros((8, num_measurements))
        print("Initial current measurements ({} samples)...".format(num_measurements))

        for measurement in range(num_measurements):
            for channel in range(8):
                status = cls.dev.get_status(channel)
                cls.I29V[channel, measurement] = status.I29V
                cls.I6V[channel, measurement] = status.I6V

        for channel in range(8):
            I29V = cls.I29V[channel, :]
            I6V = cls.I6V[channel, :]

            print("Channel {}...".format(channel))
            print("29V current: mean {:.3f} mA, min {:.3f}, max {:.3f} mA, "
                  "std {:.3f} mA".format(
                      np.mean(I29V * 1e3),
                      np.min(I29V * 1e3),
                      np.max(I29V * 1e3),
                      np.std(I29V * 1e3),
                  ))
            print("6V current: mean {:.3f} mA, min {:.3f}, max {:.3f} mA, "
                  "std {:.3f} mA".format(
                      np.mean(I6V * 1e3),
                      np.min(I6V * 1e3),
                      np.max(I6V * 1e3),
                      np.std(I6V * 1e3),
                  ))

        cls.I29V = np.mean(cls.I29V, axis=1)
        cls.I6V = np.mean(cls.I6V, axis=1)

        print("Global statistics:")
        print("29V current: mean {:.3f} mA, min {:.3f}, max {:.3f} mA, "
              "std {:.3f} mA".format(
                  np.mean(cls.I29V * 1e3),
                  np.min(cls.I29V * 1e3),
                  np.max(cls.I29V * 1e3),
                  np.std(cls.I29V * 1e3),
              ))
        print("6V current: mean {:.3f} mA, min {:.3f}, max {:.3f} mA, "
              "std {:.3f} mA".format(
                  np.mean(cls.I6V * 1e3),
                  np.min(cls.I6V * 1e3),
                  np.max(cls.I6V * 1e3),
                  np.std(cls.I6V * 1e3),
              ))

        # get baseline measurement of amplifier gain and detector accuracy
        cls.dev.set_interlock(args.chan, 37)
        cls.synth.set_power(args.p_min)
        cls.synth.set_rf_on(True)

        time.sleep(0.3)

        Po = cls.meter.read() + 30.0  # output power
        gain_min = Po - args.p_min
        detector_err_min = cls.dev.get_output_power(args.chan) - Po
        in_detector_err_min = cls.dev.get_input_power(args.chan) - args.p_min

        cls.synth.set_power(args.p_max)
        time.sleep(0.2)

        Po = cls.meter.read() + 30.0  # output power
        gain_max = Po - args.p_max
        detector_err_max = cls.dev.get_output_power(args.chan) - Po
        in_detector_err_max = cls.dev.get_input_power(args.chan) - args.p_max

        cls.gain = 0.5 * (gain_min + gain_max)
        cls.detector_err = 0.5 * (detector_err_max + detector_err_min)
        cls.in_detector_err = 0.5 * (in_detector_err_max + in_detector_err_min)

        cls.synth.set_rf_on(False)
        time.sleep(cls.t_settle)

        print("Amp gain: {} dB (min {} dB, max {} dB)".format(
            cls.gain, gain_min, gain_max))
        print("Input detector error: {} dB ({} db - {} dB)".format(
            cls.in_detector_err, in_detector_err_min, in_detector_err_max))
        print("Output detector error: {} dB ({} db - {} dB)".format(
            cls.detector_err, detector_err_min, detector_err_max))

    def assertRange(self, val, min, max):
        self.assertTrue(val >= min and val <= max)

    def assertApproxEq(self, a, b, eps):
        if not abs(a - b) < eps:
            print("FAIL approx equal: {}, {}, {}".format(a, b, eps))
        self.assertTrue(abs(a - b) < eps)

    def _cmd(self, cmd):
        self.dev.dev.write((cmd + "\n").encode())
        resp = self.dev.dev.readline().decode().strip().lower()
        if "?" in cmd:
            return resp
        self.assertEqual(resp, "ok")

    def check_errors(func):

        def wrapped(self, *args, **kwargs):
            func(self, *args, **kwargs)
            for chan in range(8):
                status = self.dev.get_status(chan)
                self.assertTrue(status.i2c_error_count == 0)
                self.assertFalse(status.error_occurred)
                if status.enabled:
                    if chan == self.cut:
                        I29V_tol = self.I29V_cut_tol
                        I6V_tol = self.I6V_cut_tol
                    else:
                        I29V_tol = self.I29V_tol
                        I6V_tol = self.I6V_tol
                    self.assertApproxEq(status.I6V, self.I6V[chan], I6V_tol)
                    self.assertApproxEq(status.I29V, self.I29V[chan], I29V_tol)
                self.assertRange(status.temp, 20, 35)

        return wrapped

    @check_errors
    def test_channel_validation(self):
        for chan in [0.1, -1, 8, "test", False, "1e0"]:
            self.dev.dev.write("CHAN:ENAB? {}\n".format(chan).encode())
            self.assertTrue("error" in self.dev.dev.readline().decode().lower())

            # test a command that doesn't accept 'all', as this follows a
            # slightly different code path in firmware
            self.dev.dev.write("CHAN:DIAG? {}\n".format(chan).encode())
            self.assertTrue("error" in self.dev.dev.readline().decode().lower())

    @check_errors
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

        time.sleep(self.t_settle)  # let things stabilize before continuing

    @check_errors
    def test_detect_channels(self):
        chan = random.randint(0, 8)
        if chan < 8:
            self.assertTrue(self.dev.get_detected(chan))
            self.assertTrue(self.dev.get_status(chan).detected)
        else:
            self.assertEqual(self._cmd("CHAN:DET? aLl"), "255")
            for chan_idx in range(8):
                self.assertTrue(self.dev.get_status(chan_idx).detected)

    @check_errors
    def test_status(self):
        dev = self.dev

        for chan in range(8):
            status = dev.get_status(chan)

            self.assertTrue(status.detected)
            self.assertFalse(status.error_occurred)
            self.assertRange(status.temp, 20, 35)
            self.assertRange(status.fan_speed, 0, 100)
            self.assertRange(status.output_power, 0, 36)
            self.assertRange(status.input_power, -60, 0)
            self.assertRange(status.reflected_power, -20, 36)

            self.assertEqual(status.detected, dev.get_detected(chan))
            self.assertEqual(status.enabled, dev.get_enabled(chan))
            self.assertEqual(status.interlock, dev.get_interlock_tripped(chan))
            self.assertEqual(status.error_occurred, dev.get_error_occurred(chan))
            self.assertApproxEq(status.temp, dev.get_temperature(chan), 2)
            self.assertApproxEq(status.fan_speed, dev.get_fan_speed(), 2)
            self.assertApproxEq(status.output_power, dev.get_output_power(chan), 0.25)
            self.assertApproxEq(status.input_power, dev.get_input_power(chan), 0.25)
            self.assertApproxEq(status.reflected_power, dev.get_reflected_power(chan),
                                0.25)

            if status.enabled:
                self.assertRange(status.V5VMP, 4.9, 5.1)

    @check_errors
    def test_interlock(self):

        self.dev.set_enabled(args.chan, True)
        self.synth.set_rf_on(True)

        for idx in range(10):
            P_synth = random.uniform(args.p_min, args.p_max)
            offset = -1.5

            self.dev.set_interlock(args.chan, P_synth + self.gain)
            self.synth.set_power(P_synth + offset)

            time.sleep(0.2)
            self.dev.clear_interlock(args.chan)
            time.sleep(0.1)

            while not self.dev.get_interlock_tripped(args.chan):
                offset += 0.1
                self.synth.set_power(P_synth + offset)
                time.sleep(0.2)
                if offset > 1.5:
                    break

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
            self.synth.set_power(P_synth)
            self.synth.set_rf_on(True)
            self.dev.set_interlock(args.chan, 37.5)
            self.dev.clear_interlock(args.chan)

            time.sleep(0.5)

            P_meter = self.meter.read() + 30
            P_booster = self.dev.get_output_power(args.chan)
            P_in = self.dev.get_input_power(args.chan)
            gain = P_meter - P_synth
            detector_err = P_booster - P_meter
            in_detector_err = P_in - P_synth

            self.assertApproxEq(gain, self.gain, 1.0)  # 1dB non-linearity
            self.assertApproxEq(in_detector_err, self.in_detector_err, 0.5)
            self.assertApproxEq(detector_err, self.detector_err, 0.5)

        self.synth.set_rf_on(False)
        time.sleep(0.1)
        self.dev.clear_interlock(args.chan)
        time.sleep(self.t_settle)

    def test_fuzz(self):
        skip = ["test_fuzz"]
        tests = [
            method_name for method_name in dir(self)
            if (callable(getattr(self, method_name)) and method_name.startswith("test_")
                and method_name not in skip)
        ]
        num_iterations = 10000
        for test_num in range(num_iterations):
            test_idx = random.randint(0, len(tests) - 1)
            test = tests[test_idx]
            print("fuzz {} of {}: {}".format(test_num, num_iterations,
                                             tests[test_idx][5:]))
            getattr(self, test)()


if __name__ == "__main__":
    args = parser.parse_args()
    unittest.main(argv=sys.argv[0:1])
