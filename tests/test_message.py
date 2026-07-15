"""Tests for DBPMessage serialisation and validation."""

import json
import re

import pytest

from dbp import DBPMessage, InvalidMessageError, Label, Policy


class TestMessageConstruction:
    """Creating DBPMessage instances."""

    def test_minimal_message(self):
        msg = DBPMessage(id="", label=Label({"X"}), origin="alice", payload={"key": "val"})
        assert msg.label.compartments == frozenset({"X"})
        assert msg.origin == "alice"
        assert msg.payload == {"key": "val"}
        assert msg.id is not None
        assert msg.timestamp is not None

    def test_auto_generated_id_is_uuid(self):
        msg = DBPMessage(id="", label=Label({"X"}), origin="alice", payload={})
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        assert re.match(uuid_pattern, msg.id)

    def test_auto_generated_timestamp_is_iso8601(self):
        from datetime import datetime, timezone
        msg = DBPMessage(id="", label=Label({"X"}), origin="alice", payload={})
        parsed = datetime.fromisoformat(msg.timestamp)
        assert parsed.tzinfo is not None

    def test_explicit_id_and_timestamp_preserved(self):
        msg = DBPMessage(
            id="custom-id",
            label=Label({"X"}), origin="alice", payload={},
            timestamp="2025-01-01T00:00:00+00:00",
        )
        assert msg.id == "custom-id"
        assert msg.timestamp == "2025-01-01T00:00:00+00:00"

    def test_policy_defaults_to_any(self):
        msg = DBPMessage(id="", label=Label({"X"}), origin="alice", payload={})
        assert msg.policy == Policy.ANY

    def test_protocol_defaults_to_dbp_1_0(self):
        msg = DBPMessage(id="", label=Label({"X"}), origin="alice", payload={})
        assert msg.protocol == "dbp/1.0"

    def test_message_with_all_fields(self):
        msg = DBPMessage(
            id="m1",
            label=Label({"A", "B"}, policy=Policy.ALL),
            origin="bob",
            payload={"count": 42},
            policy=Policy.ALL,
            destination="charlie",
            timestamp="2025-06-15T10:00:00Z",
            protocol="dbp/2.0",
        )
        assert msg.id == "m1"
        assert msg.label.compartments == frozenset({"A", "B"})
        assert msg.label.policy == Policy.ALL
        assert msg.origin == "bob"
        assert msg.payload == {"count": 42}
        assert msg.policy == Policy.ALL
        assert msg.destination == "charlie"
        assert msg.protocol == "dbp/2.0"


class TestMessageValidation:
    """Missing required fields raise InvalidMessageError."""

    def test_missing_label_raises_error(self):
        with pytest.raises(InvalidMessageError, match="label"):
            DBPMessage(id="m1", label=None, origin="alice", payload={})

    def test_missing_origin_raises_error(self):
        with pytest.raises(InvalidMessageError, match="origin"):
            DBPMessage(id="m1", label=Label({"X"}), origin="", payload={})

    def test_missing_payload_raises_error(self):
        with pytest.raises(InvalidMessageError, match="payload"):
            DBPMessage(id="m1", label=Label({"X"}), origin="alice", payload=None)


class TestMessageSerialization:
    """Roundtrip serialization for DBPMessage."""

    def test_to_dict_and_from_dict_roundtrip(self):
        original = DBPMessage(
            id="m1",
            label=Label({"A", "B"}),
            origin="alice",
            payload={"msg": "hello"},
            policy=Policy.ANY,
            destination="bob",
            timestamp="2025-01-01T00:00:00+00:00",
        )
        data = original.to_dict()
        restored = DBPMessage.from_dict(data)
        assert restored.id == original.id
        assert restored.label.compartments == original.label.compartments
        assert restored.label.policy == original.label.policy
        assert restored.origin == original.origin
        assert restored.payload == original.payload
        assert restored.policy == original.policy
        assert restored.destination == original.destination
        assert restored.timestamp == original.timestamp
        assert restored.protocol == original.protocol

    def test_to_json_and_from_json_roundtrip(self):
        original = DBPMessage(
            id="m1",
            label=Label({"engineering", "hr"}, policy=Policy.ALL),
            origin="coordinator",
            payload={"task": "review"},
            policy=Policy.ALL,
            destination="developer",
        )
        json_str = original.to_json()
        restored = DBPMessage.from_json(json_str)
        assert restored.label.compartments == original.label.compartments
        assert restored.label.policy == Policy.ALL
        assert restored.origin == "coordinator"
        assert restored.payload == {"task": "review"}
        assert restored.policy == Policy.ALL
        assert restored.destination == "developer"

    def test_label_encoding_in_dict(self):
        msg = DBPMessage(id="m1", label=Label({"A", "B"}), origin="alice", payload={})
        data = msg.to_dict()
        assert set(data["label"]["compartments"]) == {"A", "B"}
        assert data["label"]["policy"] == "any"

    def test_label_encoding_all_policy(self):
        msg = DBPMessage(id="m1", label=Label({"A"}, policy=Policy.ALL), origin="alice", payload={}, policy=Policy.ALL)
        data = msg.to_dict()
        assert data["label"]["policy"] == "all"
        assert data["policy"] == "all"

    def test_to_json_is_valid_json(self):
        msg = DBPMessage(id="m1", label=Label({"X"}), origin="alice", payload={"n": 1})
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        assert parsed["origin"] == "alice"
        assert parsed["payload"] == {"n": 1}
        assert parsed["label"]["compartments"] == ["X"]

    def test_from_json_with_missing_field_raises_error(self):
        incomplete = json.dumps({"origin": "alice"})
        with pytest.raises(InvalidMessageError):
            DBPMessage.from_json(incomplete)

    def test_from_json_with_invalid_json_raises_error(self):
        with pytest.raises(InvalidMessageError):
            DBPMessage.from_json("not-json")

    def test_from_dict_missing_label_key(self):
        with pytest.raises(InvalidMessageError):
            DBPMessage.from_dict({"origin": "alice", "payload": {}})

    def test_to_dict_contains_protocol(self):
        msg = DBPMessage(id="m1", label=Label({"X"}), origin="alice", payload={})
        assert msg.to_dict()["protocol"] == "dbp/1.0"

    def test_from_dict_default_policy_is_any(self):
        data = {
            "label": {"compartments": ["X"]},
            "origin": "alice",
            "payload": {},
        }
        msg = DBPMessage.from_dict(data)
        assert msg.policy == Policy.ANY
        assert msg.label.policy == Policy.ANY
