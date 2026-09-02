import asyncio
import json
import logging
import math
import os
import time

from .driver_raw import HolzworthSynthRaw

logger = logging.getLogger(__name__)

# Default location of the ramp state file: next to the driver source, so that it is
# picked up by the git backup of the checkout the controller runs from.
DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "Holzworth_synth_config.txt")


class HolzworthSynth:
    """Driver for the Holzworth synth driving the 674 nm quadrupole laser offset
    lock, tracking the drift of the reference cavity.

    On top of plain frequency/power control, the output frequency is continuously
    ramped at a settable rate (see :meth:`set_ramp`) to follow the cavity drift. The
    ramp is described by a reference point ``(time_freq_set, last_freq_set)`` plus the
    rate itself; the target frequency at UNIX time ``t`` is::

        last_freq_set + ramp * (t - time_freq_set)

    All three values are kept in a JSON file so that the ramp survives restarts of the
    controller, and the synth is stepped onto the resulting target every
    ``update_interval`` seconds by the task started in :meth:`start`.

    Frequency changes requested by the user do not interrupt the ramp: they shift it
    as a whole, leaving the rate and the drift accumulated so far untouched (see
    :meth:`step_freq`).

    On top of the ramp, a client (e.g. an ARTIQ experiment) can temporarily move the
    laser away from its nominal frequency in what we call an "excursion"
    (see :meth:`begin_excursion`). The excursion is an absolute offset from the ramp,
    with zero meaning the nominal frequency. It deliberately isn't stored in the ramp
    state file; the frequency is reset at the end of the excursion "session"
    (:meth:`end_excursion`)
    """

    def __init__(self, config_file=None, update_interval=10.0):
        """
        :param config_file: Path to the JSON file holding the ramp state; defaults to
            ``Holzworth_synth_config.txt`` next to this module.
        :param update_interval: Interval between periodic frequency updates, in
            seconds.
        """
        # Largest single frequency change written to the synth, in Hz; larger moves
        # are split into steps so that the laser lock survives them.
        self.max_step = 10e3
        # Tolerance for the frequency readback check, in Hz. The synth resolution is
        # 1 mHz, and both it and the raw driver round to that.
        self.freq_tolerance = 1.1e-3

        self.update_interval = update_interval
        self.config_file = DEFAULT_CONFIG_FILE if config_file is None else config_file
        # Read the ramp state before opening the device, so that a broken state file
        # does not leave a connection behind.
        self.data = self._load_config()

        self.synth_raw = HolzworthSynthRaw()  # The raw driver

        self.time_freq_updated = None

        # Temporary offset from the ramp, and the name of the client holding it (see
        # begin_excursion()).
        self._excursion = 0.0
        self._excursion_owner = None

        # Serialises everything that moves the frequency or touches self.data, so that
        # a user request and a periodic update cannot interleave halfway through a
        # multi-step move.
        self._lock = asyncio.Lock()
        self._update_task = None

    #
    # Ramp state file
    #

    def _load_config(self):
        if not os.path.isfile(self.config_file):
            raise FileNotFoundError("No ramp state file at '{}'".format(
                self.config_file))
        with open(self.config_file, "r") as f:
            try:
                data = json.load(f)
            except ValueError as e:
                raise ValueError("Could not parse ramp state file '{}': {}".format(
                    self.config_file, e)) from e
        missing = {"time_freq_set", "last_freq_set", "ramp"} - data.keys()
        if missing:
            raise ValueError("Ramp state file '{}' is missing key(s): {}".format(
                self.config_file, ", ".join(sorted(missing))))
        return data

    def _save_config(self):
        """Write the ramp state back to disk, replacing the file atomically.

        Overwriting in place would leave behind a truncated file – which the driver then
        refuses to start from – if the process died at the wrong moment.
        """
        tmp_path = self.config_file + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(self.data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.config_file)

    #
    # Ramp bookkeeping
    #

    def _ramp_freq(self, t):
        """Return the frequency the ramp calls for at UNIX time ``t``."""
        return self.data["last_freq_set"] + self.data["ramp"] * (
            t - self.data["time_freq_set"])

    def _target_freq(self, t):
        """Return the output frequency called for at UNIX time ``t``, i.e. the ramp
        plus any excursion."""
        return self._ramp_freq(t) + self._excursion

    def _check_freq_range(self, freq):
        if not self.synth_raw.min_freq <= freq <= self.synth_raw.max_freq:
            raise ValueError(
                "Requested frequency {} Hz is out of range ({} to {} Hz)".format(
                    freq, self.synth_raw.min_freq, self.synth_raw.max_freq))

    def _rebase_ramp(self, t, offset=0.0):
        """Move the ramp reference point to time ``t``, shifting the whole ramp up by
        ``offset`` Hz.

        For ``offset == 0`` the frequency trajectory is unchanged; the reference point
        is just re-expressed relative to ``t``.
        """
        self.data["last_freq_set"] = self._ramp_freq(t) + offset
        self.data["time_freq_set"] = t

    async def _move_freq(self, freq):
        """Scan the synth to ``freq`` in steps of at most ``max_step`` to keep the
        laser lock, and check that it arrived.

        The caller must hold ``self._lock``.
        """
        freq_start = self.synth_raw.get_freq()
        n_steps = math.ceil(abs(freq - freq_start) / self.max_step)
        for n in range(1, n_steps + 1):
            self.synth_raw.set_freq(freq_start + (n / n_steps) * (freq - freq_start))
            # Yield to the event loop so that the controller stays responsive during
            # long scans. The actual update rate will be set by the overhead here and
            # the USB/… overheads – not well-controlled, but the aim is only for the
            # laser not to fall out of lock.
            await asyncio.sleep(0)

        freq_actual = self.synth_raw.get_freq()
        if not math.isclose(freq_actual, freq, abs_tol=self.freq_tolerance):
            raise RuntimeError(
                "Synth did not reach the requested frequency: asked for {} Hz, "
                "read back {} Hz".format(freq, freq_actual))

    async def _update_freq(self):
        """Move the synth onto the target frequency for the current time.

        The caller must hold ``self._lock``.
        """
        await self._move_freq(self._target_freq(time.time()))
        self.time_freq_updated = time.time()

    async def _step_freq(self, delta):
        """Shift the ramp by ``delta`` Hz and move the synth accordingly.

        The caller must hold ``self._lock``.
        """
        t = time.time()
        # Check before touching the stored state; a request the synth cannot execute
        # would otherwise leave the ramp permanently pointing out of range, and every
        # subsequent update failing with it.
        self._check_freq_range(self._target_freq(t) + delta)

        self._rebase_ramp(t, offset=delta)
        # Save before moving: the file is the authoritative copy of the ramp state, so
        # if the move fails halfway the next update just carries on from there.
        self._save_config()
        await self._update_freq()

    #
    # RPC interface
    #

    async def get_freq(self):
        """Return the current output frequency of the synth, in Hz."""
        # Deliberately not taking the lock: the raw access does not yield, so a read
        # can never interleave with a step of a move that is in flight, and status
        # polling stays responsive while a long scan is running.
        return self.synth_raw.get_freq()

    async def set_freq(self, freq):
        """Set the output frequency to ``freq`` (in Hz), leaving the drift ramp
        running.

        The request is applied as a shift of the ramp by the difference between
        ``freq`` and the current output frequency, so the drift accumulated so far is
        preserved rather than being thrown away (see :meth:`step_freq`). Any excursion
        stays on top of the shifted ramp.
        """
        async with self._lock:
            await self._step_freq(freq - self.synth_raw.get_freq())

    async def step_freq(self, delta):
        """Shift the output frequency by ``delta`` Hz, leaving the drift ramp
        running.

        The ramp is shifted as a whole: the rate is untouched, and the offset persists
        across the periodic updates rather than being undone by the next one. This is
        the permanent counterpart to an excursion, which is left untouched.
        """
        async with self._lock:
            await self._step_freq(delta)

    def begin_excursion(self, owner: str):
        """Open an excursion session for ``owner``, allowing the output frequency to
        be temporarily moved away from the ramp with :meth:`set_excursion`.

        This is effectively a no-op as far as the hardware is concerned, but helps
        track potential conflicts if different experiments were to try and use this at
        the same time.

        If a session from a different owner is still open, it is currently taken over
        with a warning being logged. This is to gracefully handle e.g. experiment
        crashes, although we could tighten this up in the future. Repeat calls with the
        current owner are silent no-ops, so several parts of one experiment can share a
        session by agreeing on the name.

        :param owner: Free-form name identifying the client, used to match up the
            :meth:`set_excursion`/:meth:`end_excursion` calls and for diagnostics.
        """
        if self._excursion_owner == owner:
            return
        if self._excursion_owner is not None:
            logger.warning(
                "Excursion session from '%s' taken over by '%s' "
                "(excursion currently %.3f Hz)",
                self._excursion_owner,
                owner,
                self._excursion,
            )
        else:
            logger.info("Excursion session started by '%s'", owner)
        self._excursion_owner = owner

    async def set_excursion(self, owner: str, excursion: float):
        """Move the output frequency to ``excursion`` Hz away from the drift ramp.

        The excursion is absolute (zero being the nominal frequency), so setting the
        same value again does not move the synth. The ramp keeps running underneath;
        its periodic updates and :meth:`step_freq`/:meth:`set_freq` keep the excursion
        on top.

        :param owner: Name the session was opened with; see :meth:`begin_excursion`.
        """
        async with self._lock:
            if self._excursion_owner is None:
                raise RuntimeError(
                    "No excursion session open; call begin_excursion() first")
            if self._excursion_owner != owner:
                raise RuntimeError("Excursion session is held by '{}', not '{}'".format(
                    self._excursion_owner, owner))
            self._check_freq_range(self._ramp_freq(time.time()) + excursion)
            if excursion != self._excursion:
                logger.info("Excursion set (by '%s') to %.3f Hz", owner, excursion)
            # Set before moving, so that a move failing halfway is completed by the
            # next periodic update (as for step_freq()).
            self._excursion = excursion
            await self._update_freq()

    async def end_excursion(self, owner):
        """End the excursion session, returning the output frequency to the drift ramp.

        Does nothing if no session is open, so that clients can call it from every
        cleanup path. A session held by a different owner is left alone (with a
        warning): the call is then a stale cleanup from a previous client, and the
        current owner is responsible for ending its own session.

        :param owner: Name the session was opened with; see :meth:`begin_excursion`.
        """
        async with self._lock:
            if self._excursion_owner is None:
                return
            if self._excursion_owner != owner:
                logger.warning(
                    "Ignoring end of excursion session by '%s'; the session is held by "
                    "'%s'",
                    owner,
                    self._excursion_owner,
                )
                return
            logger.info(
                "Excursion session ended by '%s (excursion was %.3f Hz, zeroing)",
                owner,
                self._excursion,
            )
            self._excursion = 0.0
            self._excursion_owner = None
            await self._update_freq()

    def get_excursion(self):
        """Return the current excursion from the drift ramp, in Hz (zero if no
        session is open)."""
        return self._excursion

    def get_excursion_owner(self):
        """Return the owner of the open excursion session, or ``None`` if there is
        none."""
        return self._excursion_owner

    async def update_freq(self):
        """Move the synth onto the frequency the drift ramp calls for right now."""
        async with self._lock:
            await self._update_freq()

    def get_ramp(self):
        """Return the drift compensation rate, in Hz/s."""
        return self.data["ramp"]

    async def set_ramp(self, ramp):
        """Set the drift compensation rate to ``ramp`` (in Hz/s), keeping the current
        output frequency."""
        async with self._lock:
            # Re-anchor the ramp first; the reference point can be arbitrarily old, so
            # changing the rate without doing so would jump the output frequency.
            self._rebase_ramp(time.time())
            self.data["ramp"] = ramp
            self._save_config()
            await self._update_freq()

    def get_target_freq(self):
        """Return the frequency called for right now, in Hz, i.e. the drift ramp plus
        any excursion.

        The output frequency follows this in steps of ``update_interval``, so the two
        differ by up to one update worth of drift.
        """
        return self._target_freq(time.time())

    def get_time_freq_set(self):
        """Return the UNIX time of the ramp reference point."""
        return self.data["time_freq_set"]

    def get_last_freq_set(self):
        """Return the frequency of the ramp reference point, in Hz."""
        return self.data["last_freq_set"]

    def get_time_freq_updated(self):
        """Return the UNIX time of the last successful frequency update, or ``None``
        if there has not been one yet."""
        return self.time_freq_updated

    async def get_pow(self):
        """Return the current output power of the synth, in dBm."""
        return self.synth_raw.get_pow()

    async def set_pow(self, power):
        """Set the output power of the synth to ``power`` (in dBm)."""
        self.synth_raw.set_pow(power)

    def identity(self):
        """Return the device identification string."""
        return self.synth_raw.identity()

    async def ping(self):
        """Master needs to be able to ping the device."""
        return self.synth_raw.ping()

    #
    # Lifecycle
    #

    async def start(self):
        """Move the synth onto the drift ramp and start tracking it.

        To be called once from the event loop the controller runs on, before serving any
        requests.
        """
        if self._update_task is not None:
            raise RuntimeError("Frequency update task already running")

        jump = self._target_freq(time.time()) - self.synth_raw.get_freq()
        if abs(jump) > self.max_step:
            logger.warning(
                "Drift ramp calls for a jump of %.3f Hz from the current output "
                "frequency; check that '%s' is not stale",
                jump,
                self.config_file,
            )

        await self.update_freq()
        self._update_task = asyncio.ensure_future(self._run_update_loop())

    async def _run_update_loop(self):
        """Follow the drift ramp until cancelled."""
        while True:
            await asyncio.sleep(self.update_interval)
            try:
                await self.update_freq()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Keep going; a failed update just leaves the next one a bit more to
                # do. (Bailing out here would silently stop tracking the drift.)
                logger.exception("Error updating frequency, retrying in %s s",
                                 self.update_interval)

    async def stop(self):
        """Stop tracking the drift ramp."""
        if self._update_task is None:
            return
        task, self._update_task = self._update_task, None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def close(self):
        if self._update_task is not None:
            self._update_task.cancel()
            self._update_task = None
        self.synth_raw.close()
