"""
Generic driver for communicating with an MQTT broker beyond the stabilizer.
Mostly wrapping gmqtt clients for convenience.
Requires `gmqtt`
"""
# TODO: Unify with the existing driver in the previous file.

import logging
import asyncio
import json
import uuid

from contextlib import suppress
from typing import NamedTuple, List, Any, Optional
from collections.abc import Iterable
from gmqtt import Client as MqttClient, Message as MqttMessage

logger = logging.getLogger(__name__)


def _int_to_bytes(i):
    return i.to_bytes(i.bit_length() // 8 + 1, byteorder="little")


class NetworkAddress(NamedTuple):
    ip: List[int]
    port: int = 9293

    @classmethod
    def from_str_ip(cls, ip: str, port: int):
        _ip = list(map(int, ip.split(".")))
        return cls(_ip, port)

    def get_ip(self) -> str:
        return ".".join(map(str, self.ip))

    def is_unspecified(self):
        """
        Mirrors `smoltcp::wire::IpAddress::is_unspecified` in Rust for compatibility
        with stabilizer, for IPv4 addresses
        """
        return self.ip == [0, 0, 0, 0]


NetworkAddress.UNSPECIFIED = NetworkAddress([0, 0, 0, 0], 0)


class MqttInterface:
    """
    Wraps a gmqtt Client to provide a request/response-type interface using the MQTT 5
    response topics/correlation data machinery.

    A timeout is also applied to every request (which is necessary for robustness, as
    Stabilizer only supports QoS 0 for now).
    """

    def __init__(self, topic_base: str, broker_address: NetworkAddress, *args,
                 **kwargs):
        r"""
        Factory method to create a new MQTT connection
            :param broker_address: Address of the MQTT broker
            :type broker_address: NetworkAddress
            :param topic_base: Base topic of the device to connect to.
            :type topic_base: str
            :param args: Additional arguments to pass to the constructor

            :Keyword Arguments:
                * *will_message* (``gmqtt.Message``) -- Last will and testament message
                * *timeout* (``float``) -- Connection timeout
                * *maxsize* (``int``) -- Max number of mqtt requests awaiting response
                * *kwargs* -- Additional keyword arguments to pass to the constructor

            :return: A new instance of MqttInterface
        """
        will_message: Optional[MqttMessage] = kwargs.pop("will_message", None)
        self._timeout: Optional[float] = kwargs.pop("timeout", None)
        self._maxsize: Optional[int] = kwargs.pop("maxsize", 512)

        self._client = MqttClient(client_id="", will_message=will_message)

        self.broker_address = broker_address
        self._topic_base = topic_base

        #: Stores, for each in-flight RPC request, the future waiting for a response,
        #: indexed by the sequence id we used as the MQTT correlation data.
        self._pending = dict[bytes, asyncio.Future]()

        #: Use incrementing sequence id as correlation data to map
        #: responses to requests.
        self._next_seq_id = 0

        self._timeout = 2.0

        # Generate a random client ID (no real reason to use UUID here over another
        # source of randomness).
        client_id = str(uuid.uuid4()).split("-")[0]
        self._response_base = f"{topic_base}/response_{client_id}"
        self._client.on_message = self._on_message
        self._on_message_override = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_args):
        await self.disconnect()

    async def connect(self):
        host, port = self.broker_address.get_ip(), self.broker_address.port
        try:
            await self._client.connect(host, port=port, keepalive=10)
            logger.debug(f"Connected to MQTT broker at {host}:{port}.")
        except Exception as connect_exception:
            logger.error("Failed to connect to MQTT broker: %s", connect_exception)
            raise connect_exception
        self._client.subscribe(f"{self._response_base}/#")

    async def disconnect(self):
        await self._client.disconnect()

    def publish(self, topic, value, retain=True):
        """Publish a setting without waiting for a hardware response.

        This is e.g. appropriate for publishing UI changes.
        """
        payload = json.dumps(value).encode("utf-8")
        self._client.publish(f"{self._topic_base}/{topic}",
                             payload,
                             qos=0,
                             retain=retain)

    async def request(self, topic: str, argument: Any, retain: bool = False):
        """Send a request to Stabilizer and wait for the response.
        """
        if len(self._pending) > self._maxsize:
            # By construction, `correlation_data` should always be removed from
            # `_pending` either by `_on_message()` or after `_timeout`. If something
            # goes wrong, however, the dictionary could grow indefinitely.
            raise RuntimeError("Too many unhandled requests")
        result = asyncio.Future()
        correlation_data = _int_to_bytes(self._next_seq_id)

        self._pending[correlation_data] = result

        payload = json.dumps(argument).encode("utf-8")
        self._client.publish(
            f"{self._topic_base}/{topic}",
            payload,
            qos=0,
            retain=retain,
            response_topic=f"{self._response_base}/{topic}",
            correlation_data=correlation_data,
        )
        self._next_seq_id += 1

        async def fail_after_timeout():
            await asyncio.sleep(self._timeout)
            result.set_exception(
                TimeoutError(f"No response to {topic} request after {self._timeout} s"))
            self._pending.pop(correlation_data)

        _, pending = await asyncio.wait(
            [result, asyncio.create_task(fail_after_timeout())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for p in pending:
            p.cancel()
            with suppress(asyncio.CancelledError):
                await p
        return await result

    def _on_message(self, client, topic, payload, qos, properties) -> int:
        if self._on_message_override is not None:
            return self._on_message_override(client, topic, payload, qos, properties)

        if not topic.startswith(self._response_base):
            logger.debug("Ignoring unrelated topic: %s", topic)
            return 0

        cd = properties.get("correlation_data", [])
        if len(cd) != 1:
            logger.warning(
                ("Received response without (valid) correlation data"
                 "(topic '%s', payload %s) "),
                topic,
                payload,
            )
            return 0
        seq_id = cd[0]

        if seq_id not in self._pending:
            # This is fine if Stabilizer restarts, though.
            logger.warning("Received unexpected/late response for '%s' (id %s)", topic,
                           seq_id)
            return 0

        result = self._pending.pop(seq_id)
        if not result.cancelled():
            try:
                # Would like to json.loads() here, but the miniconf responses are
                # unfortunately plain strings still (see quartiq/miniconf#32).
                result.set_result(payload)
            except BaseException as e:
                err = ValueError(f"Failed to parse response for '{topic}'")
                err.__cause__ = e
                result.set_exception(err)
        return 0

    async def lookup_retained_topics(self, topics):
        """
        Subscribes to given topics and checks if it gets a response within a short
        timeout window.
        """
        if not isinstance(topics, Iterable):
            topics = [topics]

        def full_topic(topic):
            return f"{self._topic_base}/{topic}"

        decoded_values = [None for _ in topics]
        for (i, topic) in enumerate(topics):
            event = asyncio.Event()
            decoded_value = None

            def decoder(_client, topic, value, _qos, _properties):
                nonlocal decoded_value
                decoded_value = json.loads(value)
                event.set()
                return 0

            self._on_message_override = decoder
            self._client.subscribe(full_topic(topic))

            try:
                await asyncio.wait_for(event.wait(), self._timeout)
            except TimeoutError:
                logging.warning(f"Timed out waiting to read topic: {full_topic(topic)}")
            finally:
                self._client.unsubscribe(full_topic(topic))
                self._on_message_override = None
            decoded_values[i] = decoded_value

        return decoded_values
