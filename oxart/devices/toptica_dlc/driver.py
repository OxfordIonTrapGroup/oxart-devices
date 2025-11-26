#!/usr/bin/env python3
import asyncio
from asyncio import wait_for
import logging

logger = logging.getLogger(__name__)

LOCK_STATE_PARAM = "laser1:dl:lock:state"


class TopticaDLC:

    def __init__(self, dlc_client, timeout=10):
        """
        :param dlc_client: toptica.lasersdk.dlcpro.vXXX.DLCpro context with
        an active connection
        """
        self.dlc = dlc_client
        self.last_known_lock_state = 0
        self.timeout = timeout

    def __del__(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.close())

    async def __aenter__(self):
        await self.open()

    async def __aexit__(self):
        await self.close()

    async def open(self):
        logger.info("Trying to connect to DLC Pro...")
        await self.dlc.open()
        logger.info("Established connection to DLC Pro")

    async def close(self):
        await self.dlc.close()
        logger.info("Disconnected from DLC Pro")

    async def get_lock_state(self) -> int:
        """Reads and returns the current operational mode of the lock module.

        Possible values are:
        0 - Idle: no scan, no lock
        1 - Scanning: scan controller enabled
        2 - Selecting: "Scanning" plus an additional evaluating signal to find the
            lockpoint candidates
        3 - Selected: "Selecting" plus one lockpoint candidate selected as actual
            lockpoint
        4 - Locking: start of locking procedure; scanning to the lockpoint and
            activating
            the PID controller(s).
        5 - Locked: scan controller deactivated and PID lock(s) closed
        6 - On Hold: PIDs on hold, waiting for being activated again
        7 - Resetting: PIDs are being reset
        8 - Reset: PIDs reset and on hold, waiting for being actived again
        9 - Relocking: relock engine is scanning, trying to relock the PIDs

        :raises ConnectionError: when unable to read the latest lock state
        """
        try:
            self.last_known_lock_state = await wait_for(self.dlc.get(
                LOCK_STATE_PARAM, float),
                                                        timeout=self.timeout)
        except Exception as exception:
            logger.error(f"Is DLC pro connected to network?: {exception}")
            raise ConnectionError

        return self.last_known_lock_state

    async def is_locked(self) -> bool:
        """Reads the current lock state.

        :returns: Bool -- True if locked.
        """
        await self.get_lock_state()
        return self.last_known_lock_state == 5

    async def ping(self) -> bool:
        try:
            await self.get_lock_state()
            return True
        except Exception:
            logger.exception("Dummy call in ping() failed")
            return False
