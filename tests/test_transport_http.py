"""Tests for HTTPTransport — header encoding, boundary check, middleware."""

from unittest.mock import MagicMock, patch

import pytest

from dbp import (
    AgentCard,
    Boundary,
    BoundaryResult,
    Clearance,
    DBPMessage,
    Label,
    Policy,
)
from dbp.transport.http import HTTPTransport


_MSG_ID = "test-msg"


@pytest.fixture
def boundary():
    return Boundary()


@pytest.fixture
def transport(boundary):
    return HTTPTransport(boundary)


@pytest.fixture
def sender():
    return AgentCard(name="alice", clearance=Clearance({"A", "B"}))


class TestHTTPSend:
    """send() performs boundary check before HTTP request."""

    def test_send_pass_makes_request(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"A"}),
            endpoint="http://localhost:9999/api",
        )
        msg = DBPMessage(id=_MSG_ID, label=Label({"A"}), origin="alice", payload={})

        with patch("dbp.transport.http.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            result = transport.send(msg, sender, recipient)

        assert result == BoundaryResult.PASS
        mock_urlopen.assert_called_once()

    def test_send_block_skips_http_request(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"C"}),  # no overlap with {A}
            endpoint="http://localhost:9999/api",
        )
        msg = DBPMessage(id=_MSG_ID, label=Label({"A"}), origin="alice", payload={})

        with patch("dbp.transport.http.urllib.request.urlopen") as mock_urlopen:
            result = transport.send(msg, sender, recipient)

        assert result == BoundaryResult.BLOCK
        mock_urlopen.assert_not_called()

    def test_send_all_policy_block_skips_request(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"A"}),
            endpoint="http://localhost:9999/api",
        )
        msg = DBPMessage(
            id=_MSG_ID,
            label=Label({"A", "B"}, policy=Policy.ALL),
            origin="alice",
            payload={},
            policy=Policy.ALL,
        )

        with patch("dbp.transport.http.urllib.request.urlopen") as mock_urlopen:
            result = transport.send(msg, sender, recipient)

        assert result == BoundaryResult.BLOCK
        mock_urlopen.assert_not_called()

    def test_send_missing_endpoint_raises_value_error(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"A"}),
            endpoint=None,
        )
        msg = DBPMessage(id=_MSG_ID, label=Label({"A"}), origin="alice", payload={})

        with pytest.raises(ValueError, match="no endpoint"):
            transport.send(msg, sender, recipient)

    def test_send_block_without_endpoint_does_not_raise(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"C"}),  # BLOCK
            endpoint=None,
        )
        msg = DBPMessage(id=_MSG_ID, label=Label({"A"}), origin="alice", payload={})

        result = transport.send(msg, sender, recipient)
        assert result == BoundaryResult.BLOCK

    def _get_header(self, req, name):
        """Case-insensitive header lookup (Python 3.14 compat)."""
        for k, v in req.header_items():
            if k.lower() == name.lower():
                return v
        return None

    def test_send_passes_origin_header(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"A"}),
            endpoint="http://localhost:9999/api",
        )
        msg = DBPMessage(id=_MSG_ID, label=Label({"A"}), origin="alice", payload={})

        with patch("dbp.transport.http.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            transport.send(msg, sender, recipient)

        call_args = mock_urlopen.call_args[0][0]
        assert self._get_header(call_args, "X-DBP-Origin") == "alice"

    def test_send_sets_correct_headers(self, transport, sender):
        recipient = AgentCard(
            name="bob",
            clearance=Clearance({"A"}),
            endpoint="http://localhost:9999/api",
        )
        msg = DBPMessage(id=_MSG_ID, label=Label({"A", "B"}), origin="alice", payload={})

        with patch("dbp.transport.http.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = MagicMock()
            transport.send(msg, sender, recipient)

        call_args = mock_urlopen.call_args[0][0]
        assert self._get_header(call_args, "X-DBP-Label") == "A,B"
        assert self._get_header(call_args, "X-DBP-Policy") == "any"
        assert self._get_header(call_args, "Content-Type") == "application/json"

    def test_receive_returns_empty_list(self, transport):
        card = AgentCard(name="agent", clearance=Clearance({"X"}))
        assert transport.receive(card) == []


class TestHeaderHelpers:
    """label_to_header / header_to_label roundtrip."""

    def test_label_to_header_comma_separated(self):
        label = Label({"B", "A"})
        header = HTTPTransport.label_to_header(label)
        parts = header.split(",")
        assert set(parts) == {"A", "B"}

    def test_label_to_header_single_compartment(self):
        label = Label({"X"})
        header = HTTPTransport.label_to_header(label)
        assert header == "X"

    def test_label_to_header_empty(self):
        label = Label(set())
        header = HTTPTransport.label_to_header(label)
        assert header == ""

    def test_header_to_label_roundtrip(self):
        original = Label({"engineering", "hr"}, policy=Policy.ALL)
        header = HTTPTransport.label_to_header(original)
        restored = HTTPTransport.header_to_label(header, "all")
        assert restored.compartments == original.compartments
        assert restored.policy == Policy.ALL

    def test_header_to_label_default_policy(self):
        label = HTTPTransport.header_to_label("a,b", "")
        assert label.policy == Policy.ANY

    def test_header_to_label_explicit_policy(self):
        label = HTTPTransport.header_to_label("x", "all")
        assert label.policy == Policy.ALL

    def test_header_to_label_empty_string(self):
        label = HTTPTransport.header_to_label("", "any")
        assert label.compartments == frozenset()


class TestMiddleware:
    """HTTP middleware for boundary enforcement."""

    def make_request(self, label_header="", policy_header="any"):
        req = MagicMock()
        req.headers.get.side_effect = lambda name, default=None: {
            HTTPTransport.LABEL_HEADER: label_header,
            HTTPTransport.POLICY_HEADER: policy_header,
        }.get(name, default)
        return req

    def test_middleware_returns_none_on_pass(self, transport):
        card = AgentCard(name="bob", clearance=Clearance({"A"}))
        mw = transport.middleware(card)
        request = self.make_request(label_header="A", policy_header="any")
        result = mw(request)
        assert result is None

    def test_middleware_returns_403_on_block(self, transport):
        card = AgentCard(name="bob", clearance=Clearance({"X"}))
        mw = transport.middleware(card)
        request = self.make_request(label_header="Y", policy_header="any")
        result = mw(request)
        assert result is not None
        assert result["status"] == 403
        assert "DBP" in result["error"]

    def test_middleware_all_policy_block(self, transport):
        card = AgentCard(name="bob", clearance=Clearance({"A"}))
        mw = transport.middleware(card)
        request = self.make_request(label_header="A,B", policy_header="all")
        result = mw(request)
        assert result is not None
        assert result["status"] == 403

    def test_middleware_all_policy_pass(self, transport):
        card = AgentCard(name="bob", clearance=Clearance({"A", "B"}))
        mw = transport.middleware(card)
        request = self.make_request(label_header="A,B", policy_header="all")
        result = mw(request)
        assert result is None

    def test_middleware_empty_label_always_passes(self, transport):
        card = AgentCard(name="bob", clearance=Clearance({"secret"}))
        mw = transport.middleware(card)
        request = self.make_request(label_header="", policy_header="all")
        result = mw(request)
        assert result is None

    def test_middleware_trace_is_recorded(self, transport):
        card = AgentCard(name="bob", clearance=Clearance({"X"}))
        mw = transport.middleware(card)

        request_pass = self.make_request(label_header="X", policy_header="any")
        mw(request_pass)

        request_block = self.make_request(label_header="Y", policy_header="any")
        mw(request_block)

        assert len(transport.boundary.trace_log) == 2
        assert transport.boundary.trace_log[0].result == BoundaryResult.PASS
        assert transport.boundary.trace_log[1].result == BoundaryResult.BLOCK
