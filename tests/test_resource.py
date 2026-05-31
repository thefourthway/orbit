# type: ignore
# mypy: ignore-errors
# pyright: reportGeneralTypeIssues=false

from autobahn.twisted.websocket import (
    WebSocketClientFactory,
    WebSocketClientProtocol,
    connectWS,
)
from twisted.internet import defer, reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ResponseDone
from twisted.web.server import Site

from orbit import SimpleTransaction, WSProtocol, WSResource


class EchoProtocol(WSProtocol):
    def __init__(self):
        self.messages = []
        self.closes = []

    def connectionMade(self, client):
        client = client()
        if client is not None:
            client.writeText("ready")

    def dataReceived(self, client, payload, isBinary):
        self.messages.append((payload, isBinary))
        client.writeText(f"echo:{payload}")

    def onClose(self, wasClean, code, reason):
        self.closes.append((wasClean, code, reason))


class RecordingClient(WebSocketClientProtocol):
    finished = None

    def onMessage(self, payload, isBinary):
        text = payload.decode()
        if text == "ready":
            self.sendMessage(b"ping")
        elif text == "echo:ping" and self.finished is not None:
            self.finished.callback(text)


class BodyCollector(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.chunks = []

    def dataReceived(self, data):
        self.chunks.append(data)

    def connectionLost(self, reason):
        if reason.check(ResponseDone):
            self.finished.callback(b"".join(self.chunks))
        else:
            self.finished.errback(reason)


def collectBody(response):
    finished = defer.Deferred()
    response.deliverBody(BodyCollector(finished))
    return finished


@defer.inlineCallbacks
def test_ws_resource_accepts_upgrade_and_binds_transaction():
    tx = SimpleTransaction(EchoProtocol)
    lookups = []
    resource = WSResource(lambda txid: lookups.append(txid) or tx)
    port = reactor.listenTCP(0, Site(resource), interface="127.0.0.1")
    finished = defer.Deferred()

    try:
        wsPort = port.getHost().port
        factory = WebSocketClientFactory(f"ws://127.0.0.1:{wsPort}/?tx=abc")
        factory.protocol = RecordingClient
        factory.protocol.finished = finished
        connectWS(factory)

        result = yield finished

        assert result == "echo:ping"
        assert lookups == ["abc"]
        [(session, proto)] = list(tx.connections())
        assert session.transaction() is tx
        assert proto.messages == [("ping", False)]
    finally:
        tx.finish()
        yield defer.maybeDeferred(port.stopListening)


@defer.inlineCallbacks
def test_ws_resource_uses_none_when_query_param_missing():
    tx = SimpleTransaction(EchoProtocol)
    lookups = []
    resource = WSResource(lambda txid: lookups.append(txid) or tx)
    port = reactor.listenTCP(0, Site(resource), interface="127.0.0.1")
    finished = defer.Deferred()

    try:
        wsPort = port.getHost().port
        factory = WebSocketClientFactory(f"ws://127.0.0.1:{wsPort}/")
        factory.protocol = RecordingClient
        factory.protocol.finished = finished
        connectWS(factory)

        yield finished

        assert lookups == [None]
    finally:
        tx.finish()
        yield defer.maybeDeferred(port.stopListening)


@defer.inlineCallbacks
def test_ws_resource_rejects_when_lookup_returns_none():
    resource = WSResource(lambda txid: None)
    port = reactor.listenTCP(0, Site(resource), interface="127.0.0.1")

    try:
        wsPort = port.getHost().port
        agent = Agent(reactor)
        response = yield agent.request(b"GET", f"http://127.0.0.1:{wsPort}/?tx=abc".encode())
        body = yield collectBody(response)

        assert response.code == 404
        assert body == b"Transaction not found"
    finally:
        yield defer.maybeDeferred(port.stopListening)


@defer.inlineCallbacks
def test_ws_resource_honors_custom_get_param():
    tx = SimpleTransaction(EchoProtocol)
    lookups = []
    resource = WSResource(lambda txid: lookups.append(txid) or tx, getParam="room")
    port = reactor.listenTCP(0, Site(resource), interface="127.0.0.1")
    finished = defer.Deferred()

    try:
        wsPort = port.getHost().port
        factory = WebSocketClientFactory(f"ws://127.0.0.1:{wsPort}/?room=lobby")
        factory.protocol = RecordingClient
        factory.protocol.finished = finished
        connectWS(factory)

        yield finished

        assert lookups == ["lobby"]
    finally:
        tx.finish()
        yield defer.maybeDeferred(port.stopListening)
