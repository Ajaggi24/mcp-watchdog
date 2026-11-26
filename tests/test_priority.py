import json
import sys
from pathlib import Path

import pytest

from mcpwatchdog import diff_tools
from mcpwatchdog.gate import ApprovalStore, Gate
from mcpwatchdog.priority import Priority, assess_changes, assess_new_tool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench"))
from evaluate import evaluate  # noqa: E402

DEFS = ROOT / "demo_server" / "defs"


def test_demo_change_orders_file_path_first(tmp_path):
    v1 = json.loads((DEFS / "v1_approved.json").read_text())
    v2 = json.loads((DEFS / "v2_changed.json").read_text())
    gate = Gate(ApprovalStore(tmp_path / "a.json"), "srv")
    gate.update(v1)
    gate.approve_all()
    gate.update(v2)
    queue = gate.report.pending
    assert [t.name for t in queue] == ["read_note", "search_docs"]
    assert queue[0].priority is Priority.HIGH and queue[1].priority is Priority.LOW
    assert "file_path" in queue[0].assessment.reason


def test_preexisting_sensitive_text_does_not_reescalate():
    before = {"name": "t", "description": "Reads ~/.config/app.toml for settings."}
    after = {"name": "t", "description": "Reads ~/.config/app.toml for its settings."}
    assert assess_changes(diff_tools(before, after)).priority is Priority.LOW


def test_new_shell_tool_is_high():
    tool = {"name": "run_command", "description": "Run a shell command.",
            "inputSchema": {"type": "object", "properties": {"cmd": {"type": "string"}}}}
    assert assess_new_tool(tool).priority is Priority.HIGH


def test_new_benign_tool_is_medium():
    tool = {"name": "count_words", "description": "Count words.", "inputSchema": {"type": "object", "properties": {}}}
    assert assess_new_tool(tool).priority is Priority.MEDIUM


@pytest.mark.parametrize("case_set", ["dev", "heldout", "heldout2"])
def test_benchmark_gate_never_weakened(case_set):
    """Whatever the priority, no change that needs review may be classed as 'none'."""
    m = evaluate(ROOT / "bench" / "cases" / f"{case_set}.json")
    assert m["gate"]["needs_review_missed_by_watchdog"] == 0
    assert m["gate"]["formatting_only_flagged_watchdog"] == 0


def _case(case_set, cid):
    cases = json.loads((ROOT / "bench" / "cases" / f"{case_set}.json").read_text())
    return next(c for c in cases if c["id"] == cid)


def _pred(case):
    if case["before"] is None:
        return assess_new_tool(case["after"]).priority.label
    return assess_changes(diff_tools(case["before"], case["after"])).priority.label


@pytest.mark.parametrize("cid,expected", [
    ("H14", "high"),    # write/delete capability described in prose
    ("H21", "high"),    # instruction hidden in an HTML comment
    ("H04", "low"),     # "tokens" meaning LLM tokens
    ("H11", "medium"),  # benign 'filename' field
    ("H19", "high"),    # outside email address in a non-English instruction
])
def test_v1_heldout_failures_fixed_in_v2(cid, expected):
    """Regression tests for the five v1 held-out failures. Not an evaluation: these cases were seen while fixing."""
    assert _pred(_case("heldout", cid)) == expected


def test_accented_latin_is_not_flagged_as_lookalike():
    before = {"name": "t", "description": "Traduce texto."}
    after = {"name": "t", "description": "Traduce el texto a otro idioma, por favor; también acepta inglés."}
    assert assess_changes(diff_tools(before, after)).priority is Priority.LOW


def test_cyrillic_lookalike_still_flagged():
    before = {"name": "t", "description": "List open issues."}
    after = {"name": "t", "description": "List \u043epen issues."}
    assert assess_changes(diff_tools(before, after)).priority is Priority.HIGH
