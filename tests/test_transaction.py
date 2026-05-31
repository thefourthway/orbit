# type: ignore
# mypy: ignore-errors
# pyright: reportGeneralTypeIssues=false

import weakref
from abc import ABC

import pytest

from orbit import (
    SimpleTransaction,
    SimpleTransactionManager,
    Transaction,
    WSProtocol,
    WSTransactionManager,
)


class RecordingProtocol(WSProtocol):
    def __init__(self):
        self.connection_refs = []
        self.messages = []
        self.closes = []

    def connectionMade(self, client):
        self.connection_refs.append(client)

    def dataReceived(self, client, payload, isBinary):
        self.messages.append((client, payload, isBinary))

    def onClose(self, wasClean, code, reason):
        self.closes.append((wasClean, code, reason))


class FakeSession:
    def __init__(self):
        self.protocol = None
        self.transaction = None
        self.closed = False
        self.clear_count = 0

    def setTransactionData(self, proto, tx):
        self.protocol = proto
        self.transaction = tx

    def clearTransactionData(self):
        self.protocol = None
        self.transaction = None
        self.clear_count += 1

    def close(self):
        self.closed = True


def test_abstract_types_cannot_be_instantiated():
    assert issubclass(WSProtocol, ABC)
    assert issubclass(Transaction, ABC)
    assert issubclass(WSTransactionManager, ABC)

    with pytest.raises(TypeError):
        WSProtocol()

    with pytest.raises(TypeError):
        Transaction()

    with pytest.raises(TypeError):
        WSTransactionManager()


def test_simple_transaction_adopts_session_and_exposes_snapshot_connections():
    tx = SimpleTransaction(RecordingProtocol)
    session = FakeSession()

    proto = tx.adoptWS(session)

    assert isinstance(proto, RecordingProtocol)
    assert session.protocol is proto
    assert session.transaction is tx
    assert proto.connection_refs == [weakref.ref(session)]
    assert list(tx.connections()) == [(session, proto)]


def test_simple_transaction_disconnect_removes_session():
    tx = SimpleTransaction(RecordingProtocol)
    session = FakeSession()
    tx.adoptWS(session)

    tx.protoDisconnected(session)

    assert list(tx.connections()) == []


def test_simple_transaction_finish_closes_sessions_and_notifies_protocols():
    tx = SimpleTransaction(RecordingProtocol)
    first = FakeSession()
    second = FakeSession()
    first_proto = tx.adoptWS(first)
    second_proto = tx.adoptWS(second)

    tx.finish()

    assert first.closed is True
    assert second.closed is True
    assert first.clear_count == 1
    assert second.clear_count == 1
    assert first_proto.closes == [(True, 1000, "transaction finished")]
    assert second_proto.closes == [(True, 1000, "transaction finished")]
    assert list(tx.connections()) == []


def test_simple_transaction_manager_lookup_call_and_membership():
    manager = SimpleTransactionManager()
    tx = SimpleTransaction(RecordingProtocol)

    txid = manager.addTransaction(tx, "tx-1")

    assert txid == "tx-1"
    assert manager.lookupTransaction("tx-1") is tx
    assert manager("tx-1") is tx
    assert manager(None) is None
    assert manager.hasTransaction("tx-1") is True
    assert manager.lookupTransaction("missing") is None
    assert manager.hasTransaction("missing") is False


def test_simple_transaction_manager_generates_id_when_missing():
    manager = SimpleTransactionManager()
    tx = SimpleTransaction(RecordingProtocol)

    txid = manager.addTransaction(tx)

    assert isinstance(txid, str)
    assert len(txid) == 32
    assert manager.lookupTransaction(txid) is tx
