import os

# The current conda-forge Autobahn build can report NVX support even when the
# generated CFFI module is absent. Prefer the stable pure-Python path by default.
os.environ.setdefault("AUTOBAHN_USE_NVX", "0")

from autobahn.twisted.websocket import (  # noqa: E402
    WebSocketServerFactory,
    WebSocketServerProtocol,
)

__all__ = [
    "WebSocketServerFactory",
    "WebSocketServerProtocol",
]
