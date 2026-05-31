import json
from typing import Any, cast

from orbit.autobahn_compat import WebSocketServerProtocol
from orbit.protocol import WSProtocol
from orbit.transaction import Transaction


class Session(WebSocketServerProtocol):
    def __init__(self) -> None:
        super().__init__()
        self._inner_protocol: WSProtocol | None = None
        self._inner_tx: Transaction | None = None
        self._pending_tx: Transaction | None = None
        self._txid: str | None = None
        self._closed = False
        self._finished = False

    def transaction(self) -> Transaction | None:
        return self._inner_tx

    def protocolObj(self) -> WSProtocol | None:
        return self._inner_protocol

    def setTransactionData(self, proto: WSProtocol, tx: Transaction) -> None:
        if self._inner_protocol is not None or self._inner_tx is not None:
            return
        self._inner_protocol = proto
        self._inner_tx = tx

    def setPendingTransaction(self, tx: Transaction, txid: str | None = None) -> None:
        self._pending_tx = tx
        self._txid = txid

    def clearTransactionData(self) -> None:
        self._inner_protocol = None
        self._inner_tx = None

    def tx(self) -> Transaction:
        return cast(Transaction, self._inner_tx)
        
    def onOpen(self) -> None:
        if self._pending_tx is not None:
            tx = self._pending_tx
            self._pending_tx = None
            tx.adoptWS(self)
            return

        self.close()

    def onMessage(self, payload: bytes, isBinary: bool) -> None:
        if self._inner_protocol is None:
            return

        if isBinary:
            self._inner_protocol.dataReceived(self, payload, True)
        else:
            self._inner_protocol.dataReceived(
                self, payload.decode("utf-8", errors="replace"), False
            )

    def onClose(self, wasClean: bool, code: int | None, reason: str) -> None:
        self._closed = True
        self._cleanup(wasClean, code, reason)

    def write(self, data: bytes | str, binary: bool = False) -> None:
        if isinstance(data, str):
            payload = data.encode("utf-8")
        else:
            payload = data
        self.sendMessage(payload, isBinary=binary)

    def writeText(self, data: str) -> None:
        self.write(data, False)

    def writeBinary(self, data: bytes) -> None:
        self.write(data, True)

    def writeJson(self, value: Any) -> None:
        self.writeText(json.dumps(value, separators=(",", ":")))

    def close(self, code: int = 1000, reason: str = "done") -> None:
        if not self._closed:
            self._closed = True
            self.sendClose(code=code, reason=reason)

    def _cleanup(self, was_clean: bool, code: int | None, reason: str) -> None:
        if self._finished:
            return

        self._finished = True
        proto = self._inner_protocol
        tx = self._inner_tx
        self._inner_protocol = None
        self._inner_tx = None

        if proto is not None:
            proto.onClose(was_clean, code, reason)
        if tx is not None:
            tx.protoDisconnected(self)
