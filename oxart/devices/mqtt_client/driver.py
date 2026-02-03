"""Simple driver for sending MQTT commands to a Sinara stabilizer or a mezzanine
board on it.

Requires Quartiq miniconf-mqtt package from https://github.com/quartiq/miniconf.
"""

from miniconf import Miniconf
import asyncio
import logging
from typing import Any
import nest_asyncio
import argparse

nest_asyncio.apply()

logger = logging.getLogger()


class MQTTClient:

    def __init__(self, dmgr, prefix: str, address: str, timeout: float = 1):
        """
        :param dmgr: Device manager passed in by Artiq.
        :param prefix: Prefix to the '/settings' topic for the device.
        :param address: IP adress of the device running the MQTT broker.
        """

        self.dmgr = dmgr
        self.prefix = prefix
        self.address = address
        self.timeout = timeout

        self.interface = asyncio.run(Miniconf.create(self.prefix, self.address))
        logger.info(f"Connection to broker at {self.address} established.")
        self.paths = self.list_paths()

    def _check_path(self, path: str):
        """Check that the requested path exists at topic '/settings/{path}'.

        :param path: Path to check. Does not start with '/'.
        """

        return path in self.paths

    def _cleanup_path_name(self, path: str):
        """Removes any slashes before the name of the path and checks that
        '/settings/{path}' is a valid topic."""

        if path[0] == "/":
            path = path[1:]
        assert self._check_path(
            path
        ), f"Requested path '{path}' is not a valid subtopic of '/settings'."
        return path

    def set_setting(self, setting: str, value: Any):
        """Set value of a setting.

        :param setting: name of setting (or path to setting if the topic is not directly
            under '/settings').
        :param value: value to set. Must be JSON serialisable.
        """

        setting = self._cleanup_path_name(setting)

        async def _set():
            await asyncio.wait_for(
                self.interface.set("/" + setting, value), self.timeout
            )

        asyncio.run(_set())

    def get_setting(self, setting: str):
        """Get value of a setting.

        :param setting: value of setting (or path to setting if the topic is not
            directly under '/settings').
        """

        setting = self._cleanup_path_name(setting)

        async def _get():
            res = await asyncio.wait_for(
                self.interface.get("/" + setting), self.timeout
            )
            return res

        return asyncio.run(_get())

    def list_paths(self):
        """Return a list of all the valid topics under '/settings'."""

        async def _list_paths():
            return await asyncio.wait_for(self.interface.list_paths(), self.timeout)

        paths = asyncio.run(_list_paths())

        # Last entry returned by 'interface.list_paths()' is the response topic, which
        # is not a valid path.
        return paths[:-1]

    def ping(self):

        if self.get_setting(self.paths[0]):
            return True


def get_argparser():

    parser = argparse.ArgumentParser(
        description="Test connection to MQTT server by printing a list of all topics "
        + "under :prefix:/settings."
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="Prefix of MQTT /settings topic tree, of the form "
        + "'dt/sinara/:device:/:mac_address:'",
    )
    parser.add_argument(
        "--address",
        required=True,
        help="IP address of computer hosting MQTT broker process.",
    )
    parser.add_argument(
        "--timeout",
        required=False,
        default=1,
        help="Timeout period for MQTT requests in seconds.",
    )
    return parser


def main():

    args = get_argparser().parse_args()

    client = MQTTClient(
        dmgr=None, prefix=args.prefix, address=args.address, timeout=args.timeout
    )
    settings = {}
    for path in client.paths:
        value = client.get_setting(path)
        settings[path] = value
        print(f"{path}: {value}")


if __name__ == "__main__":
    main()
