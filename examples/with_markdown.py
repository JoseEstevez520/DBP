"""LocalTransport example â€” messages written as .md files on disk."""
import tempfile

from dbp import Boundary, Clearance, Label, Policy
from dbp.agent_card import AgentCard
from dbp.message import DBPMessage
from dbp.transport.local import LocalTransport

boundary = Boundary()
transport = LocalTransport(boundary, base_path=tempfile.mkdtemp())

coach_card = AgentCard(name="coach", clearance=Clearance({"identity", "fitness"}), description="Fitness coach")
dev_card = AgentCard(name="developer", clearance=Clearance({"identity", "project"}), description="Developer")

msg = DBPMessage(
    id="msg-001",
    label=Label({"fitness"}),
    origin="coach",
    payload={"plan": "squat 5x5"},
)

result = transport.send(msg, sender=coach_card, recipient=dev_card)
print(f"Developer receives [fitness]: {result.value}")

inbox = transport.receive(dev_card)
print(f"Messages in developer's inbox: {len(inbox)}")
