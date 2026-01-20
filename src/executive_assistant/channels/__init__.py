"""Channel layer for multi-platform messaging support."""

from executive_assistant.channels.base import BaseChannel, MessageFormat
from executive_assistant.channels.telegram import TelegramChannel
from executive_assistant.channels.http import HttpChannel

__all__ = ["BaseChannel", "MessageFormat", "TelegramChannel", "HttpChannel"]
