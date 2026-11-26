"""Scripted 60-second demo: tool definitions change mid-session and calls pause.

    python demo/live_demo.py            # runs straight through
    python demo/live_demo.py --step     # press Enter between scenes (for recording)

The "agent" here is a scripted client. Watchdog sits in the client, between
the agent and the server, and decides whether each tools/call may go out.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import anyio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcpwatchdog.client import connect  # noqa: E402
from mcpwatchdog.gate import ApprovalStore, ToolPaused  # noqa: E402
from mcpwatchdog.render import BOLD, DIM, GREEN, RED, c, print_report  # noqa: E402

DEFS = ROOT / "demo_server" / "defs"


def scene(title: str, step: bool) -> None:
    if step:
        input(c("\n[Enter] ", DIM))
    print("\n" + c(f"▶ {title}", BOLD), flush=True)


async def agent_call(g, name: str, args: dict) -> None:
    print(f"  agent → {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
    try:
        result = await g.call_tool(name, args)
        print("  " + c("sent", GREEN) + f"  server replied: {result.content[0].text}")
    except ToolPaused as e:
        print("  " + c("PAUSED", RED) + f"  not sent to server: {e.report.status.value}, waiting for review")


async def main(step: bool) -> None:
    work = Path(tempfile.mkdtemp(prefix="watchdog-demo-"))
    live = work / "live_defs.json"
    shutil.copy(DEFS / "v1_approved.json", live)
    store = ApprovalStore(work / "approved.json")
    command = f"python {ROOT / 'demo_server' / 'server.py'} {live}"

    async with connect(command, store, on_report=print_report) as g:
        scene("1. Developer reviews and approves the server's two tools", step)
        g.gate.approve_all()
        print_report(g.gate.report, "after approval")

        scene("2. Agent uses the approved tools", step)
        await agent_call(g, "search_docs", {"query": "mcp"})
        await agent_call(g, "read_note", {"note_id": "n1"})

        scene("3. Mid-session, the server updates both tool definitions", step)
        print(c("  (server: search_docs gets a wording edit; read_note gains a file_path field)", DIM))
        shutil.copy(DEFS / "v2_changed.json", live)
        await g.wait_for_change()

        scene("4. Agent tries both tools again", step)
        await agent_call(g, "search_docs", {"query": "mcp"})
        await agent_call(g, "read_note", {"note_id": "n1", "file_path": "~/.aws/credentials"})

        scene("5. Server rolls back to the approved definitions", step)
        shutil.copy(DEFS / "v1_approved.json", live)
        await g.wait_for_change()
        await agent_call(g, "read_note", {"note_id": "n1"})

        scene("6. Server re-sends the same tools with JSON keys reordered", step)
        shutil.copy(DEFS / "v3_reordered.json", live)
        await g.wait_for_change()
        await agent_call(g, "search_docs", {"query": "securing"})

    shutil.rmtree(work, ignore_errors=True)
    print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", action="store_true", help="wait for Enter between scenes")
    anyio.run(main, ap.parse_args().step)
