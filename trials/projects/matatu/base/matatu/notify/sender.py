"""Handing messages to a channel."""

from ..errors import DeliveryFailed
from ..models import Message


class Channel:
    name = "channel"

    def send(self, message: Message) -> None:
        raise NotImplementedError


class OutboxChannel(Channel):
    """Keeps messages in the store's outbox, where a worker or a test can read them."""

    def __init__(self, store, name: str):
        self.store = store
        self.name = name

    def send(self, message: Message) -> None:
        if not message.to:
            raise DeliveryFailed(f"no address for {self.name}")
        self.store.outbox.append(message)


class Sender:
    """Sends through named channels."""

    def __init__(self, channels):
        self.channels = {channel.name: channel for channel in channels}

    def send(self, message: Message) -> bool:
        """Returns False if there is no such channel or the channel refused the message."""
        channel = self.channels.get(message.channel)
        if channel is None:
            return False
        try:
            channel.send(message)
        except DeliveryFailed:
            return False
        return True


def outbox_sender(store) -> Sender:
    return Sender([OutboxChannel(store, "sms")])
