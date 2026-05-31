# orbit

This library is built around long-running WebSocket connections joining,
leaving, and rejoining persistent units of work.

A transaction is a durable coordination object for one logical activity. It can
represent a notification channel for an event, a chat room with multiple users,
a game state with turns and connected players, or any other long-running unit of
work that should outlive one particular socket connection.

Clients connect to the WebSocket server with a transaction or session
identifier. The server uses that identifier to look up the existing transaction
and then adopts the new WebSocket into it. If the client disconnects and later
reconnects with the same identifier, it can rejoin the same transaction instead
of forcing the server to create a new unit of work.

Transaction IDs are intentionally external to the WebSocket session machinery.
They can be generated or stored wherever the application needs:

- by an HTTP framework such as Flask running in the same process under Twisted
- by another service before the WebSocket connection is opened
- from Redis, a database, or another shared store
- by application code that creates transactions directly

The WebSocket layer should therefore stay focused on connection lifecycle,
message delivery, and transaction adoption. It should not assume one global
transaction registry, one ID format, or one persistence backend.

The key responsibilities are:

- `Session`: handles the Autobahn/Twisted socket lifecycle and forwards
  open, message, write, close, and cleanup events.
- `Transaction`: owns the logical unit of work and decides what connected
  protocols mean for that activity.
- `WSTransactionManager`: stores and resolves transaction IDs when an
  application wants an in-process registry.
- `WSResource`: integrates with Twisted Web, resolves
  transaction IDs, takes over WebSocket upgrade requests, and attaches sessions
  to the transaction returned by the lookup function.
