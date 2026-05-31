"""Persistent units of work adopted by replaceable WebSocket sessions.

See docs/websocket_transactions.md for the project-level design notes.
"""

import weakref
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from orbit.protocol import WSProtocol
from orbit._utils import randomAsciiString

if TYPE_CHECKING:
    from orbit.session import Session


class Transaction(ABC):
    @abstractmethod
    def adoptWS(self, client: "Session") -> WSProtocol:
        raise NotImplementedError

    @abstractmethod
    def finish(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def protoDisconnected(self, client: "Session") -> None:
        raise NotImplementedError

    @abstractmethod
    def connections(self) -> Iterator[tuple["Session", WSProtocol]]:
        raise NotImplementedError


class SimpleTransaction(Transaction):
    def __init__(self, protocolFactory: Callable[[], WSProtocol]) -> None:
        self._protocolFactory = protocolFactory
        self._connections: dict[Session, WSProtocol] = {}
        self._finishing = False
        self.initialize()

    def initialize(self) -> None:
        pass

    def adoptWS(self, client: "Session") -> WSProtocol:
        proto = self._protocolFactory()
        self._connections[client] = proto
        client.setTransactionData(proto, self)
        proto.connectionMade(weakref.ref(client))
        return proto

    def finish(self) -> None:
        if self._finishing:
            return

        self._finishing = True
        try:
            for ws, proto in list(self._connections.items()):
                ws.clearTransactionData()
                ws.close()
                proto.onClose(True, 1000, "transaction finished")
            self._connections.clear()
        finally:
            self._finishing = False

    def protoDisconnected(self, client: "Session") -> None:
        if self._finishing:
            return
        self._connections.pop(client, None)

    def connections(self) -> Iterator[tuple["Session", WSProtocol]]:
        yield from list(self._connections.items())


class WSTransactionManager(ABC):
    @abstractmethod
    def addTransaction(self, tx: Transaction, txid: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def lookupTransaction(self, txid: str) -> Transaction | None:
        raise NotImplementedError

    @abstractmethod
    def hasTransaction(self, txid: str) -> bool:
        raise NotImplementedError

    def __call__(self, txid: str | None) -> Transaction | None:
        if txid is None:
            return None
        return self.lookupTransaction(txid)


class SimpleTransactionManager(WSTransactionManager):
    def __init__(self) -> None:
        self._transactions: dict[str, Transaction] = {}

    def addTransaction(self, tx: Transaction, txid: str | None = None) -> str:
        realTxid = txid if txid is not None else randomAsciiString()
        self._transactions[realTxid] = tx
        return realTxid

    def lookupTransaction(self, txid: str) -> Transaction | None:
        return self._transactions.get(txid)

    def hasTransaction(self, txid: str) -> bool:
        return txid in self._transactions
