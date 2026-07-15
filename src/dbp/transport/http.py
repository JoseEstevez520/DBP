"""HTTP transport with ``X-DBP-*`` headers.

This transport sends :class:`DBPMessage` instances over HTTP POST requests,
encoding the label and policy in custom headers.  It also provides a
:meth:`middleware` factory suitable for plugging into HTTP frameworks.

.. note::
   This module uses :mod:`urllib.request` from the standard library so that
   no third-party HTTP client is required.  For production use you may want
   to swap in ``httpx`` or ``requests``.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from ..agent_card import AgentCard
from ..boundary import Boundary
from ..message import DBPMessage
from ..primitives import BoundaryResult, Label, Policy
from .base import Transport


class HTTPTransport(Transport):
    """Transport using HTTP with ``X-DBP-*`` headers.

    Parameters
    ----------
    boundary:
        The :class:`Boundary` engine.
    """

    LABEL_HEADER = "X-DBP-Label"
    POLICY_HEADER = "X-DBP-Policy"
    ORIGIN_HEADER = "X-DBP-Origin"

    def __init__(self, boundary: Boundary) -> None:
        super().__init__(boundary)

    # -- Transport interface -------------------------------------------------

    def send(
        self,
        message: DBPMessage,
        sender: AgentCard,
        recipient: AgentCard,
    ) -> BoundaryResult:
        """Send *message* via HTTP POST with DBP headers.

        The boundary check is performed **before** the request is made.
        If the check returns ``BLOCK`` the request is not sent.

        Requires the *recipient* card to have an ``endpoint`` set.
        """
        result = self.boundary.check(
            message.label,
            recipient.clearance,
            message.policy,
            data_id=message.id,
            origin=sender.name,
            destination=recipient.name,
        )
        if result == BoundaryResult.BLOCK:
            return result

        if not recipient.endpoint:
            raise ValueError(
                f"Recipient '{recipient.name}' has no endpoint configured"
            )

        headers = {
            self.LABEL_HEADER: self.label_to_header(message.label),
            self.POLICY_HEADER: message.policy.value,
            self.ORIGIN_HEADER: sender.name,
            "Content-Type": "application/json",
        }
        body = message.to_json().encode("utf-8")
        req = urllib.request.Request(
            recipient.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        urllib.request.urlopen(req)
        return BoundaryResult.PASS

    def receive(self, agent: AgentCard) -> List[DBPMessage]:
        """Not applicable for HTTP push model.

        HTTP is push-based: the server receives requests rather than polling.
        Use :meth:`middleware` to enforce boundary checks on inbound requests.
        """
        return []

    # -- Header helpers ------------------------------------------------------

    @staticmethod
    def label_to_header(label: Label) -> str:
        """Encode a :class:`Label` as a comma-separated header value."""
        return ",".join(sorted(label.compartments))

    @staticmethod
    def header_to_label(
        header: str,
        policy_header: str = "any",
    ) -> Label:
        """Decode a label from HTTP header values.

        Parameters
        ----------
        header:
            Comma-separated compartment string from ``X-DBP-Label``.
        policy_header:
            Value of the ``X-DBP-Policy`` header (``"any"`` or ``"all"``).
        """
        compartments = frozenset(
            c.strip() for c in header.split(",") if c.strip()
        )
        policy = Policy(policy_header.lower()) if policy_header else Policy.ANY
        return Label(compartments, policy)

    # -- Middleware ----------------------------------------------------------

    def middleware(
        self,
        recipient_card: AgentCard,
    ) -> Callable[[Any], Optional[Dict[str, Any]]]:
        """Return a middleware function for HTTP frameworks.

        The middleware reads ``X-DBP-Label`` and ``X-DBP-Policy`` from the
        incoming request headers, performs a boundary check, and returns
        ``None`` (proceed) or an error dict with ``status`` 403.

        Parameters
        ----------
        recipient_card:
            The :class:`AgentCard` representing the receiving agent.

        Returns
        -------
        Callable
            A function ``(request) -> dict | None``.  The *request* object
            must support ``request.headers.get(name, default)``.
        """
        transport = self

        def dbp_middleware(request: Any) -> Optional[Dict[str, Any]]:
            label_hdr = request.headers.get(transport.LABEL_HEADER, "")
            policy_hdr = request.headers.get(transport.POLICY_HEADER, "any")
            label = transport.header_to_label(label_hdr, policy_hdr)

            result = transport.boundary.check(
                label,
                recipient_card.clearance,
                data_id=None,
                destination=recipient_card.name,
            )
            if result == BoundaryResult.BLOCK:
                return {"status": 403, "error": "DBP boundary check failed"}
            return None  # proceed

        return dbp_middleware
