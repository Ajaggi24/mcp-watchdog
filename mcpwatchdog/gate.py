"""Approval store and the call gate.

Rule: a tool may be called only if its current definition is equivalent to the
definition a developer approved. New tools and changed tools are paused until
someone reviews them. Restoring the exact approved definition un-pauses a tool
without a new approval, because it is the definition that was approved.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .diff import Change, diff_tools
from .priority import Assessment, Priority, assess_changes, assess_new_tool
from .snapshot import canonicalize, fingerprint, tool_to_dict


class Status(str, Enum):
    APPROVED = "approved"   # matches the approved snapshot
    CHANGED = "changed"     # differs from the approved snapshot -> review required
    NEW = "new"             # never approved -> review required


@dataclass
class ToolReport:
    name: str
    status: Status
    changes: list[Change] = field(default_factory=list)
    assessment: Assessment = field(default_factory=Assessment)

    @property
    def priority(self) -> Priority:
        return self.assessment.priority

    @property
    def needs_review(self) -> bool:
        return self.status is not Status.APPROVED


@dataclass
class Report:
    tools: dict[str, ToolReport]
    removed: list[str]

    @property
    def pending(self) -> list[ToolReport]:
        """Tools awaiting review, most urgent first (the review queue)."""
        items = [t for t in self.tools.values() if t.needs_review]
        return sorted(items, key=lambda t: (-t.priority, t.name))

    @property
    def clean(self) -> bool:
        return not self.pending


class ApprovalStore:
    """JSON file: {server_id: {tool_name: {definition, fingerprint, approved_at}}}."""

    def __init__(self, path: str | os.PathLike[str] = ".watchdog/approved.json"):
        self.path = Path(path)
        self._data: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        """Re-read approvals from disk (another process, e.g. `mcpwatchdog review`, may have written them)."""
        self._data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def approved(self, server_id: str) -> dict[str, dict[str, Any]]:
        return {name: rec["definition"] for name, rec in self._data.get(server_id, {}).items()}

    def approve(self, server_id: str, tool: dict[str, Any]) -> None:
        self._data.setdefault(server_id, {})[tool["name"]] = {
            "definition": canonicalize(tool),
            "fingerprint": fingerprint(tool),
            "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self._save()

    def forget(self, server_id: str, name: str) -> None:
        self._data.get(server_id, {}).pop(name, None)
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(tmp, self.path)


def evaluate(approved: dict[str, dict[str, Any]], current_tools: list[Any]) -> Report:
    """Compare the server's current tool list with the approved snapshot."""
    tools: dict[str, ToolReport] = {}
    for raw in current_tools:
        tool = tool_to_dict(raw)
        name = tool["name"]
        if name not in approved:
            tools[name] = ToolReport(name, Status.NEW, assessment=assess_new_tool(tool))
            continue
        changes = diff_tools(approved[name], tool)
        if changes:
            tools[name] = ToolReport(name, Status.CHANGED, changes, assess_changes(changes))
        else:
            tools[name] = ToolReport(name, Status.APPROVED)
    removed = sorted(set(approved) - set(tools))
    return Report(tools, removed)


class ToolPaused(Exception):
    def __init__(self, report: ToolReport):
        self.report = report
        super().__init__(f"tool '{report.name}' is paused: {report.status.value}, review required")


class Gate:
    """Holds the latest report for one server and decides whether a call may go out."""

    def __init__(self, store: ApprovalStore, server_id: str):
        self.store = store
        self.server_id = server_id
        self.current: dict[str, dict[str, Any]] = {}
        self.report = Report({}, [])

    def update(self, current_tools: list[Any]) -> Report:
        self.current = {t["name"]: t for t in map(tool_to_dict, current_tools)}
        self.report = evaluate(self.store.approved(self.server_id), list(self.current.values()))
        return self.report

    def check(self, name: str) -> None:
        rep = self.report.tools.get(name)
        if rep is None:
            raise KeyError(f"unknown tool '{name}'")
        if rep.needs_review:
            raise ToolPaused(rep)

    def approve(self, name: str) -> None:
        """Record a developer's approval of the tool's *current* definition."""
        self.store.approve(self.server_id, self.current[name])
        self.update(list(self.current.values()))

    def approve_all(self) -> None:
        for name in list(self.current):
            self.store.approve(self.server_id, self.current[name])
        self.update(list(self.current.values()))
