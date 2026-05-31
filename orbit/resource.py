from collections.abc import Callable
from typing import Any

from twisted.protocols.policies import ProtocolWrapper
from twisted.web.pages import notFound
from twisted.web.resource import IResource
from twisted.web.server import NOT_DONE_YET
from zope.interface import implementer

from orbit.autobahn_compat import WebSocketServerFactory
from orbit.session import Session
from orbit.transaction import Transaction


TransactionLookup = Callable[[str | None], Transaction | None]


class WSFactory(WebSocketServerFactory):
    protocol = Session


@implementer(IResource)
class WSResource:
    isLeaf = True

    def __init__(
        self,
        txLookup: TransactionLookup,
        getParam: str = "tx",
        url: str = "ws://localhost",
    ) -> None:
        self._txLookup = txLookup
        self._getParam = getParam
        self._factory = WSFactory(url)

    def getChildWithDefault(self, name: bytes, request: Any) -> Any:
        return notFound(message="No such child resource.")

    def putChild(self, path: bytes, child: Any) -> None:
        pass

    def render(self, request: Any) -> bytes | int:
        txid = self._requestTxid(request)
        tx = self._txLookup(txid)
        if tx is None:
            request.setResponseCode(404, b"Transaction not found")
            request.setHeader(b"connection", b"close")
            return b"Transaction not found"

        if request.channel.transport is None:
            request.setResponseCode(426, b"Upgrade required")
            request.setHeader(b"upgrade", b"websocket")
            request.setHeader(b"connection", b"close")
            return b"WebSocket upgrade required"

        protocol = self._factory.buildProtocol(request.transport.getPeer())
        if protocol is None:
            request.setResponseCode(500)
            request.setHeader(b"connection", b"close")
            return b""

        if isinstance(protocol, Session):
            protocol.setPendingTransaction(tx, txid)

        transport, request.channel.transport = request.channel.transport, None

        if isinstance(transport, ProtocolWrapper):
            transport.wrappedProtocol = protocol
        elif isinstance(transport.protocol, ProtocolWrapper):
            transport.protocol.wrappedProtocol = protocol
        else:
            transport.protocol = protocol

        protocol.makeConnection(transport)

        if hasattr(transport, "_networkProducer"):
            transport._networkProducer.resumeProducing()
        elif hasattr(transport, "resumeProducing"):
            transport.resumeProducing()

        protocol.dataReceived(self._rawRequestBytes(request))

        return NOT_DONE_YET

    def _requestTxid(self, request: Any) -> str | None:
        key = self._getParam.encode()
        if key not in request.args:
            return None

        values = request.args[key]
        if not values:
            return ""

        return values[0].decode("utf-8", errors="replace")

    def _rawRequestBytes(self, request: Any) -> bytes:
        data = request.method + b" " + request.uri + b" HTTP/1.1\r\n"
        for name, values in request.requestHeaders.getAllRawHeaders():
            data += name + b": " + b",".join(values) + b"\r\n"
        data += b"\r\n"
        data += request.content.read()
        return data
