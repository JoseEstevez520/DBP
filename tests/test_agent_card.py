"""Tests for AgentCard serialisation and construction."""

import json

import pytest

from dbp import AgentCard, Clearance


class TestAgentCardConstruction:
    """Creating AgentCard instances."""

    def test_construction_with_clearance(self):
        card = AgentCard(name="coach", clearance=Clearance({"fitness", "identity"}))
        assert card.name == "coach"
        assert card.clearance.compartments == frozenset({"fitness", "identity"})

    def test_default_protocol(self):
        card = AgentCard(
            name="test", clearance=Clearance({"X"})
        )
        assert card.protocol == "dbp/1.0"

    def test_default_description(self):
        card = AgentCard(name="test", clearance=Clearance({"X"}))
        assert card.description == ""

    def test_default_endpoint_none(self):
        card = AgentCard(name="test", clearance=Clearance({"X"}))
        assert card.endpoint is None

    def test_default_auth_none(self):
        card = AgentCard(name="test", clearance=Clearance({"X"}))
        assert card.auth is None

    def test_all_fields_explicit(self):
        card = AgentCard(
            name="agent-x",
            clearance=Clearance({"sec"}),
            description="Security agent",
            endpoint="http://localhost:9000",
            auth={"type": "bearer", "key": "abc"},
            protocol="dbp/2.0",
        )
        assert card.name == "agent-x"
        assert card.clearance.compartments == frozenset({"sec"})
        assert card.description == "Security agent"
        assert card.endpoint == "http://localhost:9000"
        assert card.auth == {"type": "bearer", "key": "abc"}
        assert card.protocol == "dbp/2.0"


class TestAgentCardSerialization:
    """AgentCard to_dict / from_dict roundtrip."""

    def test_to_dict_and_from_dict_roundtrip(self):
        original = AgentCard(
            name="alice",
            clearance=Clearance({"engineering", "hr"}),
            description="Alice the agent",
            endpoint="http://localhost:8001",
            auth={"type": "api_key"},
        )
        data = original.to_dict()
        restored = AgentCard.from_dict(data)
        assert restored.name == original.name
        assert restored.clearance.compartments == original.clearance.compartments
        assert restored.description == original.description
        assert restored.endpoint == original.endpoint
        assert restored.auth == original.auth
        assert restored.protocol == original.protocol

    def test_to_dict_sorted_clearance(self):
        card = AgentCard(name="a", clearance=Clearance({"z", "a", "m"}))
        data = card.to_dict()
        # Should be sorted alphabetically
        assert data["clearance"] == sorted(["z", "a", "m"])

    def test_from_dict_without_optional_fields(self):
        data = {
            "name": "minimal",
            "clearance": ["X"],
        }
        card = AgentCard.from_dict(data)
        assert card.name == "minimal"
        assert card.clearance.compartments == frozenset({"X"})
        assert card.description == ""
        assert card.endpoint is None
        assert card.auth is None
        assert card.protocol == "dbp/1.0"

    def test_from_dict_with_all_fields(self):
        data = {
            "name": "full",
            "clearance": ["a", "b"],
            "description": "Full card",
            "endpoint": "http://endpoint",
            "auth": {"type": "none"},
            "protocol": "dbp/2.0",
        }
        card = AgentCard.from_dict(data)
        assert card.name == "full"
        assert card.protocol == "dbp/2.0"

    def test_missing_name_raises_key_error(self):
        with pytest.raises(KeyError):
            AgentCard.from_dict({"clearance": ["X"]})

    def test_missing_clearance_raises_key_error(self):
        with pytest.raises(KeyError):
            AgentCard.from_dict({"name": "test"})


class TestAgentCardFileIO:
    """AgentCard to_json_file / from_json_file."""

    def test_to_json_file_and_from_json_file_roundtrip(self, tmp_path):
        original = AgentCard(
            name="filetest",
            clearance=Clearance({"A", "B"}),
        )
        path = str(tmp_path / "cards" / "agent.json")
        original.to_json_file(path)
        assert tmp_path.joinpath("cards", "agent.json").exists()

        restored = AgentCard.from_json_file(path)
        assert restored.name == "filetest"
        assert restored.clearance.compartments == frozenset({"A", "B"})

    def test_to_json_file_creates_parent_directories(self, tmp_path):
        card = AgentCard(name="deep", clearance=Clearance({"X"}))
        path = str(tmp_path / "a" / "b" / "c" / "card.json")
        card.to_json_file(path)
        assert tmp_path.joinpath("a", "b", "c", "card.json").exists()

    def test_from_json_file_validates_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json")
        with pytest.raises(json.JSONDecodeError):
            AgentCard.from_json_file(str(path))
