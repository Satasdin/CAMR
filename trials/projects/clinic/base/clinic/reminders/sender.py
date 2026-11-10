"""Delivering messages to a channel."""

from typing import Callable, Dict, List

from ..errors import DeliveryFailed
from ..models import Message


class Sender:
    """Hands each message to the function registered for its channel."""

    def __init__(self):
        self.channels: Dict[str, Callable[[Message], None]] = {}
        self.failed: List[Message] = []

    def register(self, channel: str, deliver: Callable[[Message], None]) -> None:
        self.channels[channel] = deliver

    def send(self, message: Message) -> bool:
        """True if the channel took the message."""
        deliver = self.channels.get(message.channel)
        if deliver is None:
            self.failed.append(message)
            return False
        try:
            deliver(message)
        except DeliveryFailed:
            self.failed.append(message)
            return False
        return True


def outbox_sender(store, channels=("sms", "email")) -> Sender:
    """A sender that keeps every message in the store's outbox."""
    sender = Sender()
    for channel in channels:
        sender.register(channel, store.outbox.append)
    return sender
