import weakref
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orbit.session import Session


class WSProtocol(ABC):
    @abstractmethod
    def connectionMade(self, client: weakref.ReferenceType["Session"]) -> None:
        pass
    
    @abstractmethod
    def dataReceived(
        self,
        client: "Session",
        payload: bytes | str,
        isBinary: bool,
    ) -> None:
        pass

    @abstractmethod
    def onClose(self, wasClean: bool, code: int | None, reason: str) -> None:
        pass
