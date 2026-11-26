"""End-to-end tests against the real stdio demo server."""

import shutil
import sys
from pathlib import Path

import anyio
import pytest

from mcpwatchdog.client import connect
from mcpwatchdog.gate import ApprovalStore, ToolPaused

ROOT = Path(__file__).resolve().parents[1]
DEFS = ROOT / "demo_server" / "defs"


def _cmd(live: Path) -> str:
    return f"{sys.executable} {ROOT / 'demo_server' / 'server.py'} {live}"


def test_mid_session_change_pauses_calls(tmp_path):
    async def run():
        live = tmp_path / "live.json"
        shutil.copy(DEFS / "v1_approved.json", live)
        async with connect(_cmd(live), ApprovalStore(tmp_path / "a.json")) as g:
            g.gate.approve_all()
            await g.call_tool("read_note", {"note_id": "n1"})

            shutil.copy(DEFS / "v2_changed.json", live)
            await g.wait_for_change()
            with pytest.raises(ToolPaused):
                await g.call_tool("read_note", {"note_id": "n1", "file_path": "/etc/passwd"})

    anyio.run(run)


def test_call_racing_a_notification_is_rechecked(tmp_path):
    """A call made after list_changed arrives but before anyone re-lists must still be gated."""

    async def run():
        live = tmp_path / "live.json"
        shutil.copy(DEFS / "v1_approved.json", live)
        async with connect(_cmd(live), ApprovalStore(tmp_path / "a.json")) as g:
            g.gate.approve_all()
            shutil.copy(DEFS / "v2_changed.json", live)
            with anyio.fail_after(5):
                while not g._stale:
                    await anyio.sleep(0.05)
            with pytest.raises(ToolPaused):
                await g.call_tool("read_note", {"note_id": "n1"})

    anyio.run(run)


def test_reconnect_detects_change_made_while_disconnected(tmp_path):
    async def run():
        live = tmp_path / "live.json"
        store_path = tmp_path / "a.json"
        shutil.copy(DEFS / "v1_approved.json", live)
        async with connect(_cmd(live), ApprovalStore(store_path)) as g:
            g.gate.approve_all()
        shutil.copy(DEFS / "v2_changed.json", live)
        async with connect(_cmd(live), ApprovalStore(store_path)) as g:
            assert {r.name for r in g.gate.report.pending} == {"read_note", "search_docs"}

    anyio.run(run)
