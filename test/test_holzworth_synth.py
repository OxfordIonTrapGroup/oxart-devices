"""Unit tests for the drift-ramp and excursion logic of the Holzworth synth driver.

The driver is exercised against a stand-in for
:class:`oxart.devices.holzworth_synth.driver_raw.HolzworthSynthRaw`, so that the tests
run without the synth attached. Importing the driver is safe on any platform, as the
raw driver only touches the (Windows-only) ``ctypes.WinDLL`` in its constructor.
"""

import asyncio
import json
import os
import tempfile
import time
import unittest
from unittest import mock

from oxart.devices.holzworth_synth import driver as holzworth


class FakeHolzworthSynthRaw:
    """Stand-in for the raw driver which records every frequency written to it."""

    min_freq = 1e5
    max_freq = 2.048e9

    def __init__(self, freq):
        self.freq = round(freq, 3)
        self.writes = []
        self.power = None
        self.closed = False
        #: Number of upcoming set_freq() calls to fail, to simulate a flaky link.
        self.fail_writes = 0
        self._write_waiters = []

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        if self.fail_writes > 0:
            self.fail_writes -= 1
            raise RuntimeError("Simulated communications failure")
        if not self.min_freq <= freq <= self.max_freq:
            raise ValueError("Frequency {} Hz out of range".format(freq))
        self.freq = round(freq, 3)  # the synth resolution is 1 mHz
        self.writes.append(self.freq)
        for future, count in list(self._write_waiters):
            if len(self.writes) >= count:
                self._write_waiters.remove((future, count))
                if not future.done():
                    future.set_result(None)

    async def wait_for_writes(self, count, timeout=10.):
        """Wait until at least ``count`` frequencies have been written in total."""
        if len(self.writes) >= count:
            return
        future = asyncio.get_running_loop().create_future()
        self._write_waiters.append((future, count))
        await asyncio.wait_for(future, timeout)

    def get_pow(self):
        return -3.5

    def set_pow(self, power):
        self.power = power

    def identity(self):
        return "Holzworth Instrumentation,HS1001B,#1,1.0,SN-TEST"

    def ping(self):
        return True

    def close(self):
        self.closed = True


class HolzworthSynthTestCase(unittest.IsolatedAsyncioTestCase):
    """Common setup: a driver backed by :class:`FakeHolzworthSynthRaw` and a ramp
    state file in a temporary directory."""

    initial_freq = 142.155e6

    def setUp(self):
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.config_file = os.path.join(tmp_dir.name, "ramp_state.txt")

    def make_dev(self, ramp=0., age=0., **kwargs):
        """Create a driver whose ramp runs at ``ramp`` Hz/s from a reference point
        ``age`` seconds in the past."""
        self.write_config({
            "time_freq_set": time.time() - age,
            "last_freq_set": self.initial_freq,
            "ramp": ramp
        })
        self.raw = FakeHolzworthSynthRaw(self.initial_freq)
        with self.patch_raw(self.raw):
            dev = holzworth.HolzworthSynth(config_file=self.config_file, **kwargs)
        self.addCleanup(dev.close)
        return dev

    @staticmethod
    def patch_raw(raw=None):
        """Make the driver connect to the given stand-in instead of the synth."""
        if raw is None:
            raw = FakeHolzworthSynthRaw(HolzworthSynthTestCase.initial_freq)
        return mock.patch.object(holzworth, "HolzworthSynthRaw", lambda: raw)

    def write_config(self, data):
        with open(self.config_file, "w") as f:
            json.dump(data, f)

    def read_config(self):
        with open(self.config_file) as f:
            return json.load(f)

    @staticmethod
    def ramp_state(dev):
        """Snapshot the ramp as a function of time.

        Comparing two snapshots (see :meth:`freq_at`) shows what an operation did to
        the ramp without depending on how long the test took to run.
        """
        return (dev.get_last_freq_set(), dev.get_time_freq_set(), dev.get_ramp())

    @staticmethod
    def freq_at(state, t):
        """Return the frequency the given ramp snapshot calls for at UNIX time t."""
        last_freq_set, time_freq_set, ramp = state
        return last_freq_set + ramp * (t - time_freq_set)

    def assert_ramp_shifted_by(self, before, after, delta):
        """Assert that the ramp was displaced by ``delta`` Hz at every point in time,
        i.e. that its rate is unchanged and the shift is not undone by later
        updates."""
        self.assertEqual(after[2], before[2])
        for t in (before[1], after[1], time.time(), time.time() + 86400.):
            self.assertAlmostEqual(self.freq_at(after, t) - self.freq_at(before, t),
                                   delta,
                                   delta=1e-4)


class RampTest(HolzworthSynthTestCase):
    """Frequency requests versus the drift ramp."""

    async def test_step_freq_shifts_whole_ramp(self):
        dev = self.make_dev(ramp=0.2, age=1e6)
        await dev.update_freq()
        freq_before = self.raw.freq
        before = self.ramp_state(dev)

        await dev.step_freq(-5e3)

        self.assert_ramp_shifted_by(before, self.ramp_state(dev), -5e3)
        self.assertAlmostEqual(self.raw.freq, freq_before - 5e3, delta=1.)

    async def test_set_freq_applies_delta_from_current(self):
        dev = self.make_dev(ramp=0.2, age=1e6)
        await dev.update_freq()
        # The ramp has drifted a long way from the reference point by now; the drift
        # must survive the set_freq() below rather than being thrown away.
        self.assertAlmostEqual(self.raw.freq - dev.get_last_freq_set(), 2e5, delta=1.)
        before = self.ramp_state(dev)

        target = await dev.get_freq() + 12345.
        await dev.set_freq(target)

        self.assert_ramp_shifted_by(before, self.ramp_state(dev), 12345.)
        self.assertAlmostEqual(self.raw.freq, target, delta=1.)

    async def test_set_freq_concurrent_with_update(self):
        """Regression test: a frequency request and a periodic update used to
        interleave their scans, so that each ended up checking the frequency the
        other one had just written and failed.
        """
        dev = self.make_dev(ramp=1e3, age=1e3)

        # Both of these are long scans in opposite directions, so they are guaranteed
        # to interleave at the points where _move_freq() yields.
        await asyncio.gather(dev.set_freq(143e6), dev.update_freq())

        # Either order is legitimate, but the synth must end up on the resulting ramp.
        self.assertAlmostEqual(self.raw.freq, dev.get_target_freq(), delta=100.)

    async def test_concurrent_requests_are_serialised(self):
        dev = self.make_dev(ramp=10.)
        await asyncio.gather(dev.step_freq(1e6), dev.step_freq(-0.5e6),
                             dev.update_freq(), dev.set_freq(142.0e6))
        # Whichever order they ran in, the last one left the synth on the ramp.
        self.assertAlmostEqual(self.raw.freq, dev.get_target_freq(), delta=1.)

    async def test_moves_are_split_into_steps(self):
        dev = self.make_dev()
        await dev.step_freq(1e6)

        previous = [self.initial_freq] + self.raw.writes[:-1]
        self.assertLessEqual(max(abs(b - a) for a, b in zip(previous, self.raw.writes)),
                             dev.max_step)
        self.assertEqual(len(self.raw.writes), int(1e6 / dev.max_step))

    async def test_set_ramp_preserves_frequency(self):
        dev = self.make_dev(ramp=0.2, age=1e7)
        await dev.update_freq()
        freq_before = self.raw.freq
        before = self.ramp_state(dev)

        await dev.set_ramp(-50.)

        after = self.ramp_state(dev)
        self.assertEqual(after[2], -50.)
        # The ramp is re-anchored at the current frequency, so changing the rate does
        # not jump the output even though the old reference point is months old.
        self.assertAlmostEqual(self.freq_at(after, after[1]),
                               self.freq_at(before, after[1]),
                               delta=1e-4)
        self.assertAlmostEqual(self.raw.freq, freq_before, delta=1.)

    async def test_out_of_range_request_leaves_ramp_untouched(self):
        dev = self.make_dev(ramp=0.2)
        before = self.read_config()

        with self.assertRaises(ValueError):
            await dev.set_freq(3e9)

        self.assertEqual(self.read_config(), before)
        await dev.update_freq()  # the ramp is still usable

    async def test_readback_mismatch_is_reported(self):
        dev = self.make_dev()
        with mock.patch.object(self.raw, "set_freq", lambda freq: None):
            with self.assertRaisesRegex(RuntimeError, "did not reach"):
                await dev.step_freq(1e3)


class RampStateFileTest(HolzworthSynthTestCase):
    """Persistence of the ramp across restarts."""

    async def test_ramp_survives_restart(self):
        dev = self.make_dev(ramp=10.)
        await dev.step_freq(1e3)
        state = self.ramp_state(dev)
        dev.close()

        raw = FakeHolzworthSynthRaw(self.raw.freq)
        with self.patch_raw(raw):
            restarted = holzworth.HolzworthSynth(config_file=self.config_file)
        self.addCleanup(restarted.close)
        self.assertEqual(self.ramp_state(restarted), state)

        await restarted.update_freq()
        self.assertAlmostEqual(raw.freq, self.freq_at(state, time.time()), delta=1.)

    async def test_write_leaves_previous_state_intact_on_failure(self):
        dev = self.make_dev(ramp=1.)
        before = self.read_config()

        with mock.patch.object(json, "dump", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                await dev.step_freq(1.)

        # The state file is replaced atomically, so a failed write cannot leave behind
        # a truncated file (which the driver would refuse to start from).
        self.assertEqual(self.read_config(), before)

    def test_missing_state_file(self):
        with self.patch_raw():
            with self.assertRaises(FileNotFoundError):
                holzworth.HolzworthSynth(config_file=self.config_file)

    def test_unparsable_state_file(self):
        with open(self.config_file, "w"):
            pass
        with self.patch_raw():
            with self.assertRaisesRegex(ValueError, "Could not parse"):
                holzworth.HolzworthSynth(config_file=self.config_file)

    def test_incomplete_state_file(self):
        self.write_config({"ramp": 1.})
        with self.patch_raw():
            with self.assertRaisesRegex(ValueError, "last_freq_set, time_freq_set"):
                holzworth.HolzworthSynth(config_file=self.config_file)


class UpdateLoopTest(HolzworthSynthTestCase):
    """The task tracking the ramp while the controller is running."""

    async def test_updates_continue_after_error(self):
        dev = self.make_dev(ramp=1e3, update_interval=0.)
        await dev.start()
        self.addAsyncCleanup(dev.stop)
        await self.raw.wait_for_writes(1)

        self.raw.fail_writes = 1
        with self.assertLogs(holzworth.logger, "ERROR"):
            await self.raw.wait_for_writes(len(self.raw.writes) + 1)
        self.assertFalse(dev._update_task.done())

    async def test_start_moves_onto_ramp(self):
        dev = self.make_dev(ramp=0.2, age=1e6)
        # The reference point is old enough that the ramp calls for a large jump,
        # which the user should be warned about in case the state file is stale.
        with self.assertLogs(holzworth.logger, "WARNING"):
            await dev.start()
        self.addAsyncCleanup(dev.stop)

        self.assertAlmostEqual(self.raw.freq, dev.get_target_freq(), delta=1.)
        self.assertIsNotNone(dev.get_time_freq_updated())
        with self.assertRaises(RuntimeError):
            await dev.start()

    async def test_stop_is_idempotent(self):
        dev = self.make_dev(update_interval=0.)
        await dev.start()
        await dev.stop()
        await dev.stop()
        self.assertIsNone(dev._update_task)


class DeviceAccessTest(HolzworthSynthTestCase):
    """Plain pass-throughs to the raw driver."""

    async def test_frequency_and_power(self):
        dev = self.make_dev()
        self.assertEqual(await dev.get_freq(), self.initial_freq)
        self.assertEqual(await dev.get_pow(), -3.5)
        await dev.set_pow(-10.)
        self.assertEqual(self.raw.power, -10.)

    async def test_ping_and_identity(self):
        dev = self.make_dev()
        self.assertTrue(await dev.ping())
        self.assertIn("HS1001B", dev.identity())

    async def test_close(self):
        dev = self.make_dev(update_interval=0.)
        await dev.start()
        dev.close()
        self.assertTrue(self.raw.closed)
        self.assertIsNone(dev._update_task)


class ExcursionTest(HolzworthSynthTestCase):
    """Temporary excursions from the drift ramp."""

    async def test_excursion_moves_synth_and_leaves_ramp(self):
        dev = self.make_dev(ramp=0.2, age=1e6)
        await dev.update_freq()
        before = self.ramp_state(dev)
        config_before = self.read_config()

        dev.begin_excursion("exp")
        await dev.set_excursion("exp", -5e3)

        self.assertAlmostEqual(self.raw.freq, dev.get_target_freq(), delta=1.)
        self.assertAlmostEqual(self.raw.freq,
                               self.freq_at(before, time.time()) - 5e3,
                               delta=1.)
        self.assertEqual(dev.get_excursion(), -5e3)
        self.assertEqual(dev.get_excursion_owner(), "exp")
        # The ramp itself is untouched, both in memory and on disk.
        self.assertEqual(self.ramp_state(dev), before)
        self.assertEqual(self.read_config(), config_before)

    async def test_excursion_is_absolute(self):
        dev = self.make_dev()
        dev.begin_excursion("exp")
        await dev.set_excursion("exp", -5e3)

        # Setting the same value again does not touch the synth.
        num_writes = len(self.raw.writes)
        await dev.set_excursion("exp", -5e3)
        self.assertEqual(len(self.raw.writes), num_writes)

        # A different value moves by the difference, not by the value.
        await dev.set_excursion("exp", -8e3)
        self.assertAlmostEqual(self.raw.freq, self.initial_freq - 8e3, delta=1.)

    async def test_end_excursion_returns_to_ramp(self):
        dev = self.make_dev(ramp=0.2, age=1e6)
        dev.begin_excursion("exp")
        await dev.set_excursion("exp", -5e3)

        await dev.end_excursion("exp")
        self.assertEqual(dev.get_excursion(), 0.)
        self.assertIsNone(dev.get_excursion_owner())
        self.assertAlmostEqual(self.raw.freq,
                               self.freq_at(self.ramp_state(dev), time.time()),
                               delta=1.)

        # Ending again (e.g. from a second cleanup path) is a no-op.
        num_writes = len(self.raw.writes)
        await dev.end_excursion("exp")
        self.assertEqual(len(self.raw.writes), num_writes)

    async def test_set_excursion_requires_session(self):
        dev = self.make_dev()
        with self.assertRaises(RuntimeError):
            await dev.set_excursion("exp", 1e3)

        dev.begin_excursion("exp")
        await dev.set_excursion("exp", 1e3)
        await dev.end_excursion("exp")
        with self.assertRaises(RuntimeError):
            await dev.set_excursion("exp", 1e3)
        self.assertAlmostEqual(self.raw.freq, self.initial_freq, delta=1.)

    async def test_session_owner(self):
        dev = self.make_dev()
        dev.begin_excursion("a")
        await dev.set_excursion("a", 1e3)

        # Beginning again for the same owner is fine (e.g. several fragments of one
        # experiment sharing a session).
        with self.assertNoLogs(holzworth.logger, "WARNING"):
            dev.begin_excursion("a")
        self.assertEqual(dev.get_excursion(), 1e3)

        # Other clients can neither set nor end it…
        with self.assertRaises(RuntimeError):
            await dev.set_excursion("b", 2e3)
        with self.assertLogs(holzworth.logger, "WARNING"):
            await dev.end_excursion("b")
        self.assertEqual(dev.get_excursion_owner(), "a")
        self.assertEqual(dev.get_excursion(), 1e3)

        # …but can take it over (e.g. after the previous experiment crashed), which
        # keeps the excursion until they set their own.
        with self.assertLogs(holzworth.logger, "WARNING"):
            dev.begin_excursion("b")
        self.assertEqual(dev.get_excursion_owner(), "b")
        self.assertEqual(dev.get_excursion(), 1e3)
        await dev.set_excursion("b", 2e3)
        self.assertAlmostEqual(self.raw.freq, self.initial_freq + 2e3, delta=1.)

    async def test_ramp_keeps_running_under_excursion(self):
        dev = self.make_dev(ramp=0.2, age=1e6)
        dev.begin_excursion("exp")
        await dev.set_excursion("exp", -5e3)
        before = self.ramp_state(dev)

        # Permanent changes go to the ramp; the excursion stays on top.
        await dev.step_freq(1e3)
        self.assert_ramp_shifted_by(before, self.ramp_state(dev), 1e3)
        self.assertEqual(dev.get_excursion(), -5e3)
        self.assertAlmostEqual(self.raw.freq,
                               self.freq_at(before, time.time()) + 1e3 - 5e3,
                               delta=1.)

        # As do the periodic updates.
        await dev.update_freq()
        self.assertAlmostEqual(self.raw.freq,
                               self.freq_at(self.ramp_state(dev), time.time()) - 5e3,
                               delta=1.)

        # set_freq() sets the actual output, i.e. the shift goes to the ramp as well.
        target = await dev.get_freq() + 12345.
        await dev.set_freq(target)
        self.assertAlmostEqual(self.raw.freq, target, delta=1.)
        self.assertEqual(dev.get_excursion(), -5e3)

        await dev.end_excursion("exp")
        self.assertAlmostEqual(self.raw.freq, target + 5e3, delta=1.)
        self.assertAlmostEqual(self.raw.freq,
                               self.freq_at(self.ramp_state(dev), time.time()),
                               delta=1.)

    async def test_excursion_is_not_persisted(self):
        dev = self.make_dev(ramp=0.2)
        dev.begin_excursion("exp")
        await dev.set_excursion("exp", -5e3)
        state = self.ramp_state(dev)
        dev.close()

        raw = FakeHolzworthSynthRaw(self.raw.freq)
        with self.patch_raw(raw):
            restarted = holzworth.HolzworthSynth(config_file=self.config_file)
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.get_excursion(), 0.)
        self.assertIsNone(restarted.get_excursion_owner())
        self.assertEqual(self.ramp_state(restarted), state)

        # The restarted controller returns to the nominal ramp.
        await restarted.update_freq()
        self.assertAlmostEqual(raw.freq, self.freq_at(state, time.time()), delta=1.)

    async def test_out_of_range_excursion_rejected(self):
        dev = self.make_dev()
        dev.begin_excursion("exp")
        with self.assertRaises(ValueError):
            await dev.set_excursion("exp", 3e9)
        self.assertEqual(dev.get_excursion(), 0.)
        self.assertEqual(self.raw.writes, [])

    async def test_step_freq_range_check_includes_excursion(self):
        dev = self.make_dev()
        dev.max_step = 1e9  # Keep the (simulated) moves cheap.
        dev.begin_excursion("exp")
        await dev.set_excursion("exp", 1.9e9)
        before = self.read_config()

        with self.assertRaises(ValueError):
            await dev.step_freq(10e6)  # Would exceed the maximum frequency.
        self.assertEqual(self.read_config(), before)
        self.assertEqual(dev.get_excursion(), 1.9e9)


if __name__ == "__main__":
    unittest.main()
