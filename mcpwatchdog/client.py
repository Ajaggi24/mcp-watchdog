"""A guarded MCP client session.

Wraps the MCP SDK's ClientSession. It snapshots the tool list on connect,
re-checks it whenever the server sends `notifications/tools/list_changed`,
and refuses to send `tools/call` for any tool whose definition is not the
approved one.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import anyio
import mcp_types as types
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from .gate import ApprovalStore, Gate, Report

OnReport = Callable[[Report, str], None]


class GuardedSession:
    def __init__(self, session: ClientSession, gate: Gate, on_report: OnReport | None = None):
        self.session = session
        self.gate = gate
        self.on_report = on_report
        self._stale = False              # a list_changed arrived and we have not re-listed yet
        self._changed = anyio.Event()

    async def refresh(self, reason: str) -> Report:
        result = await self.session.list_tools()
        self._stale = False
        report = self.gate.update(result.tools)
        if self.on_report:
            self.on_report(report, reason)
        return report

    async def handle_message(self, message: Any) -> None:
        if isinstance(message, types.ToolListChangedNotification):
            # Mark stale first: any call that races with the refresh re-lists before it goes out.
            self._stale = True
            self._changed.set()

    async def wait_for_change(self, timeout: float | None = 5.0) -> Report:
        """Wait for the next tools/list_changed, then re-check. timeout=None waits forever."""
        with anyio.fail_after(timeout):
            await self._changed.wait()
        self._changed = anyio.Event()
        return await self.refresh("server sent tools/list_changed")

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> types.CallToolResult:
        if self._stale:
            await self.refresh("re-checked before call (pending list_changed)")
        self.gate.check(name)  # raises ToolPaused
        return await self.session.call_tool(name, arguments or {})


def server_params(command: str) -> StdioServerParameters:
    argv = shlex.split(command)
    if argv and argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    return StdioServerParameters(command=argv[0], args=argv[1:])


@asynccontextmanager
async def connect(
    command: str,
    store: ApprovalStore,
    server_id: str | None = None,
    on_report: OnReport | None = None,
) -> AsyncIterator[GuardedSession]:
    """Start a stdio MCP server and yield a GuardedSession with the first report computed."""
    holder: dict[str, GuardedSession] = {}

    async def handler(message: Any) -> None:
        if "g" in holder:
            await holder["g"].handle_message(message)

    async with stdio_client(server_params(command)) as (read, write):
        async with ClientSession(read, write, message_handler=handler) as session:
            init = await session.initialize()
            sid = server_id or init.server_info.name
            guarded = GuardedSession(session, Gate(store, sid), on_report)
            holder["g"] = guarded
            await guarded.refresh("connected")
            yield guarded
