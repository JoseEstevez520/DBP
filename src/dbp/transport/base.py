"""Abstract base class for DBP transports.

Every concrete transport must subclass :class:`Transport` and implement
:meth:`send` and :meth:`receive`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..agent_card import AgentCard
from ..boundary import Boundary
from ..message import DBPMessage
from ..primitives import BoundaryResult


class Transport(ABC):
    """Abstract transport that enforces boundary checks on message exchange.

    Parameters
    ----------
    boundary:
        The :class:`Boundary` engine used to evaluate labels against
        agent clearances.
    """

    def __init__(self, boundary: Boundary) -> None:
        self.boundary = boundary

    @abstractmethod
    def send(
        self,
        message: DBPMessage,
        sender: AgentCard,
        recipient: AgentCard,
    ) -> BoundaryResult:
        """Send *message* from *sender* to *recipient*.

        The implementation must perform a boundary check before delivery and
        return the :class:`BoundaryResult`.
        """
        ...

    @abstractmethod
    def receive(self, agent: AgentCard) -> List[DBPMessage]:
        """Retrieve pending messages for *agent*.

        Returns a (possibly empty) list of :class:`DBPMessage` instances
        that pass the agent's boundary check.
        """
        ...
