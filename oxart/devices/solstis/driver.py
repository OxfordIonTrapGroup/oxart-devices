import websockets
import json
from requests.exceptions import ConnectionError


class SolstisNotifier:
    def __init__(self, server, port=8088, status_callback=None, notification_callback=None):
        self.server = server
        self.port = port
        self.status_callback = status_callback
        self.notification_callback = None

    async def run(self):
        async with websockets.connect(
                    'ws://{}:{}'.format(self.server, self.port), ping_interval=None
                    ) as websocket:
            while True:
                raw_msg = await websocket.recv()
                try:
                    msg = json.loads(raw_msg)
                except json.JSONDecodeError:
                    print("Got JSONDecodeError : raw_msg = {}".format(raw_msg))
                    continue
                type_ = msg["message_type"]

                if type_ == "left_panel": # Lock, PD, and pzt status update
                    if self.status_callback:
                        self.status_callback(msg)
                elif type_ == "notification":
                    if self.notification_callback:
                        self.notification_callback(msg)

