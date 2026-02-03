import json
from asyncio import wait_for
from logging import getLogger

# Requires websockets > 15.0
from websockets.asyncio.client import connect

logger = getLogger(__name__)


class SolstisNotifier:

    def __init__(
        self,
        server,
        port=8088,
        status_callback=lambda msg: None,
        notification_callback=lambda msg: None,
        timeout=None,
    ):
        self.server = server
        self.port = port
        self.status_callback = status_callback
        self.notification_callback = notification_callback
        self.timeout = timeout

    async def run(self):
        """Connect to the Solstis websocket server and receive messages until
        connection drops."""
        logger.info("Connecting to Solstis at {}:{}".format(self.server, self.port))
        async with connect("ws://{}:{}".format(self.server, self.port),
                           ping_interval=None) as websocket:
            while True:
                try:
                    raw_msg = await wait_for(websocket.recv(), timeout=self.timeout)
                except Exception:
                    logger.warning("Could not fetch data from Solstis")
                    break
                self._handle_message(raw_msg)

        logger.warning("Disconnected from Solstis...")

    def _handle_message(self, raw_msg):
        """Process a single message from the Solstis and call the appropriate
        callback."""
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            logger.warning("Got JSONDecodeError : raw_msg = {}".format(raw_msg))
            return

        type_ = msg["message_type"]

        try:
            if type_ == "left_panel":  # Lock, PD, and pzt status update
                self.status_callback(msg)
            elif type_ == "notification":
                self.notification_callback(msg)
        except Exception:
            logger.warning("Callback failed")
