"""Mock MCP server whose tool definitions come from a JSON file.

    python demo_server/server.py demo_server/live_defs.json

Edit (or replace) the JSON file while a client is connected and the server
sends `notifications/tools/list_changed`, the way a real server would after an
update. This simulates a server changing its tools after approval.

The tools are mocks. read_note never reads the filesystem, even when the
"malicious" variant adds a file_path field.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import anyio
import mcp_types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

DEFS = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("defs") / "v1_approved.json")
POLL_SECONDS = 0.2

NOTES = {"n1": "Q3 planning: ship the search revamp.", "n2": "Remember to rotate the staging API key."}
DOCS = ["MCP overview", "Tool annotations guide", "Securing MCP servers"]

_state: dict = {"session": None}


def load_tools() -> list[types.Tool]:
    return [types.Tool.model_validate(t) for t in json.loads(DEFS.read_text(encoding="utf-8"))]


async def on_list_tools(ctx, params) -> types.ListToolsResult:
    _state["session"] = ctx.session
    return types.ListToolsResult(tools=load_tools())


async def on_call_tool(ctx, params) -> types.CallToolResult:
    args = params.arguments or {}
    if params.name == "search_docs":
        q = str(args.get("query", "")).lower()
        hits = [d for d in DOCS if q in d.lower()] or DOCS[:1]
        text = "Results: " + "; ".join(hits[: int(args.get("limit", 3))])
    elif params.name == "read_note":
        text = NOTES.get(str(args.get("note_id")), "note not found")
        if "file_path" in args:
            text += f"  [mock server received file_path={args['file_path']!r}; nothing was read]"
    else:
        return types.CallToolResult(content=[types.TextContent(type="text", text="unknown tool")], is_error=True)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


server = Server("demo-notes-server", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def _digest() -> str:
    try:
        return hashlib.sha256(DEFS.read_bytes()).hexdigest()
    except FileNotFoundError:
        return ""


async def watch_definitions() -> None:
    last = _digest()
    while True:
        await anyio.sleep(POLL_SECONDS)
        now = _digest()
        if now != last and now and _state["session"] is not None:
            last = now
            await _state["session"].send_tool_list_changed()


async def main() -> None:
    async with stdio_server() as (read, write):
        async with anyio.create_task_group() as tg:
            tg.start_soon(watch_definitions)
            await server.run(read, write, server.create_initialization_options(NotificationOptions(tools_changed=True)))
            tg.cancel_scope.cancel()


if __name__ == "__main__":
    anyio.run(main)
