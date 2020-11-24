import asyncio
from asyncio import wait_for
import time

from toptica.lasersdk.asyncio.dlcpro.v2_0_1 import Client, NetworkConnection

class TopticaDLCpro:
    def __init__(self,
                 server,
                 parameters = {},
                 write_point=None,
                 poll = 30,
                 timeout=None):
        self.server = server
        self.parameters = parameters
        self.write_point = write_point
        self.poll = poll
        self.timeout = timeout

    async def run(self):
        msg = {key : None for key in self.parameters.keys()}
        async with Client(NetworkConnection(self.server)) as dlc:
            last_update = time.time()
            while True:
                t = time.time()
                if t >= last_update + self.poll:
                    for key in self.parameters.keys():
                        try:
                            msg[key] = await wait_for(dlc.get(self.parameters[key], float),
                                                        timeout = self.timeout)
                        except:
                             print('Error: Is DLC pro connected to network?')
                    self.write_point(msg)
                    last_update = t