"""HTTPTransport setup example — demonstrates configuration, no real HTTP calls."""
from unittest.mock import patch

from dbp import Boundary, Clearance, Label, Policy
from dbp.agent_card import AgentCard
from dbp.message import DBPMessage
from dbp.transport.http import HTTPTransport

boundary = Boundary()
transport = HTTPTransport(boundary)

developer_card = AgentCard(
    name="developer",
    clearance=Clearance({"identity", "project", "schedule"}),
    endpoint="http://localhost:9001/webhook",
)

msg = DBPMessage(
    id="msg-042",
    label=Label({"project"}),
    origin="ci-bot",
    payload={"pr": 42, "status": "ready"},
)

with patch("urllib.request.urlopen") as mock_urlopen:
    result = transport.send(msg, sender=developer_card, recipient=developer_card)
    print(f"Message would have been sent: {result.value}")
    print(f"Would POST to: {developer_card.endpoint}")

middleware = transport.middleware(developer_card)

class FakeRequest:
    headers = {"X-DBP-Label": "identity,schedule", "X-DBP-Policy": "any"}

blocked = middleware(FakeRequest())
print(f"Inbound identity+schedule -> developer: {'BLOCKED' if blocked else 'ALLOWED'}")
