"""End-to-end: a plain MCP client (standing in for Claude Code / Cursor) talks to
`mcpwatchdog proxy`, which talks to the demo server."""

import shutil
import sys
from pathlib import Path

import anyio
import mcp_types as types
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcpwatchdog.client import connect
from mcpwatchdog.gate import ApprovalStore

ROOT = Path(__file__).resolve().parents[1]
DEFS = ROOT / "demo_server" / "defs"


def test_proxy_hides_unapproved_tools_and_reloads_approvals(tmp_path):
    live, store = tmp_path / "live.json", tmp_path / "approved.json"
    shutil.copy(DEFS / "v1_approved.json", live)
    upstream = f"{sys.executable} {ROOT / 'demo_server' / 'server.py'} {live}"

    async def approve_current():
        async with connect(upstream, ApprovalStore(store)) as g:
            g.gate.approve_all()

    async def run():
        await approve_current()
        changed = anyio.Event()
        box = {"ev": changed}

        async def handler(msg):
            if isinstance(msg, types.ToolListChangedNotification):
                box["ev"].set()

        async def wait_changed():
            with anyio.fail_after(10):
                await box["ev"].wait()
            box["ev"] = anyio.Event()

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcpwatchdog", "proxy", "--server", upstream, "--store", str(store),
                  "--html", str(tmp_path / "review.html"), "--poll", "0.2"],
            cwd=str(ROOT))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w, message_handler=handler) as host:
                await host.initialize()

                # 1. approved tools are visible and callable through the proxy
                tools = (await host.list_tools()).tools
                assert sorted(t.name for t in tools) == ["read_note", "search_docs"]
                res = await host.call_tool("read_note", {"note_id": "n1"})
                assert not res.is_error and "Q3 planning" in res.content[0].text

                # 2. upstream changes both tools mid-session -> host is notified, tools withheld
                shutil.copy(DEFS / "v2_changed.json", live)
                await wait_changed()
                tools = (await host.list_tools()).tools
                assert tools == []  # the model never sees the unapproved descriptions
                res = await host.call_tool("read_note", {"note_id": "n1", "file_path": "~/.aws/credentials"})
                assert res.is_error and "paused by MCP Watchdog" in res.content[0].text
                assert "priority: high" in res.content[0].text
                assert (tmp_path / "review.html").exists()

                # 3. a developer approves in another process -> proxy reloads, tools come back
                await approve_current()
                await wait_changed()
                tools = {t.name: t for t in (await host.list_tools()).tools}
                assert sorted(tools) == ["read_note", "search_docs"]
                assert "file_path" in tools["read_note"].input_schema["properties"]

    anyio.run(run)
