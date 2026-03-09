"""Web runtime support for browser-based clients."""

from .api import create_app
from .runtime import WebRuntime

__all__ = ["WebRuntime", "create_app"]
