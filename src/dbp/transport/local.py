"""Local file-based transport using Markdown files with YAML frontmatter.

Messages are stored as ``.md`` files in a shared directory.  The DBP label
and policy are encoded in the YAML frontmatter so they survive at rest and
are human-readable.

File layout::

    <base_path>/
        <message-id>.md      # one file per message
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..agent_card import AgentCard
from ..boundary import Boundary
from ..message import DBPMessage
from ..primitives import BoundaryResult, Label, Policy
from .base import Transport

# Regex for splitting YAML frontmatter from body
_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$",
    re.DOTALL,
)


class LocalTransport(Transport):
    """File-system transport that stores messages as Markdown files.

    Parameters
    ----------
    boundary:
        The :class:`Boundary` engine.
    base_path:
        Directory where message files are stored.
    """

    def __init__(self, boundary: Boundary, base_path: Union[str, Path]) -> None:
        super().__init__(boundary)
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    # -- Transport interface -------------------------------------------------

    def send(
        self,
        message: DBPMessage,
        sender: AgentCard,
        recipient: AgentCard,
    ) -> BoundaryResult:
        """Write *message* as a ``.md`` file if the boundary check passes.

        Returns the :class:`BoundaryResult`.
        """
        result = self.boundary.check(
            message.label,
            recipient.clearance,
            message.policy,
            data_id=message.id,
            origin=sender.name,
            destination=recipient.name,
        )
        if result == BoundaryResult.PASS:
            path = self.base_path / f"{message.id}.md"
            self.write_with_frontmatter(
                path=path,
                label=message.label,
                policy=message.policy,
                content=json.dumps(message.to_dict(), indent=2),
            )
        return result

    def receive(self, agent: AgentCard) -> List[DBPMessage]:
        """Read all ``.md`` files whose label passes the agent's boundary check."""
        messages: List[DBPMessage] = []
        for path in sorted(self.base_path.glob("*.md")):
            fm = self.read_frontmatter(path)
            if fm is None:
                continue
            label = Label(
                compartments=fm.get("compartments", []),
                policy=Policy(fm.get("policy", "any")),
            )
            result = self.boundary.check(
                label,
                agent.clearance,
                data_id=path.stem,
                destination=agent.name,
            )
            if result == BoundaryResult.PASS:
                body = self._read_body(path)
                try:
                    msg = DBPMessage.from_json(body)
                    messages.append(msg)
                except Exception:
                    # Skip malformed messages
                    continue
        return messages

    # -- Frontmatter helpers -------------------------------------------------

    @staticmethod
    def read_frontmatter(path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Extract DBP metadata from YAML frontmatter of a Markdown file.

        Returns ``None`` if the file has no valid frontmatter.
        """
        text = Path(path).read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if not match:
            return None
        # Minimal YAML parsing (key: value pairs only -- avoids PyYAML dep)
        fm: Dict[str, Any] = {}
        for line in match.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            # Handle list values written as JSON-style arrays
            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                fm[key] = [
                    v.strip().strip("\"'") for v in inner.split(",") if v.strip()
                ] if inner else []
            else:
                fm[key] = value.strip("\"'")
        return fm

    @staticmethod
    def write_with_frontmatter(
        path: Union[str, Path],
        label: Label,
        policy: Policy,
        content: str,
    ) -> None:
        """Write a Markdown file with DBP YAML frontmatter.

        Parameters
        ----------
        path:
            Destination file path.
        label:
            The :class:`Label` to encode in frontmatter.
        policy:
            The :class:`Policy` to encode.
        content:
            The Markdown body (may contain the JSON payload).
        """
        compartments = sorted(label.compartments)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "---",
            f"compartments: {json.dumps(compartments)}",
            f"policy: {policy.value}",
            "---",
            "",
            content,
        ]
        p.write_text("\n".join(lines), encoding="utf-8")

    # -- internal ------------------------------------------------------------

    @staticmethod
    def _read_body(path: Path) -> str:
        """Return the body (everything after frontmatter) of a Markdown file."""
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(text)
        if match:
            return match.group(2)
        return text
