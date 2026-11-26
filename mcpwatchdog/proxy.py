"""Proxy mode: run Watchdog in front of a real MCP host (Claude Code, Cursor, ...).

    host  <-- stdio -->  mcpwatchdog proxy  <-- stdio -->  upstream MCP server

The host launches the proxy as if it were the MCP server. The proxy starts the
real server itself and:

  * lists to the host ONLY tools whose current definition matches an approved
    snapshot. A changed or new tool is withheld, so the model never reads
    unapproved description text, not just never calls it;
  * refuses calls to withheld tools with an error that says review is needed;
  * forwards the upstream's tools/list_changed to the host;
  * reloads the approval store when it changes on disk, so approving with
    `mcpwatchdog review` in another terminal takes effect without a restart;
  * logs every check to stderr and writes the review page (--html).

stdout is the MCP channel to the host, so nothing here may print to it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
import mcp_types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from .client import connect
from .gate import ApprovalStore, Report, ToolPaused
from .html import render_html
from .render import render_report


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _error(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=True)


async def run_proxy(upstream: str, store_path: str, server_id: str | None = None,
                    html_path: str | None = None, poll_seconds: float = 1.0) -> None:
    store = ApprovalStore(store_path)
    downstream: dict = {"session": None}

    def on_report(report: Report, reason: str) -> None:
        _log("[mcp-watchdog] " + render_report(report, reason))
        if html_path and report.pending:
            Path(html_path).parent.mkdir(parents=True, exist_ok=True)
            Path(html_path).write_text(render_html(report, server_id or ""), encoding="utf-8")
            _log(f"[mcp-watchdog] review page: {html_path}")

    async with connect(upstream, store, server_id, on_report=on_report) as g:
        if g.gate.report.pending:
            _log(f"[mcp-watchdog] {len(g.gate.report.pending)} tool(s) withheld until reviewed. Approve with:\n"
                 f'  python -m mcpwatchdog review --server "{upstream}" --store {store_path}')

        async def notify_host() -> None:
            session = downstream["session"]
            if session is not None:
                await session.send_tool_list_changed()

        async def on_list_tools(ctx, params) -> types.ListToolsResult:
            downstream["session"] = ctx.session
            if g._stale:
                await g.refresh("re-checked before listing (pending list_changed)")
            visible = [types.Tool.model_validate(g.gate.current[name])
                       for name, rep in sorted(g.gate.report.tools.items()) if not rep.needs_review]
            return types.ListToolsResult(tools=visible)

        async def on_call_tool(ctx, params) -> types.CallToolResult:
            downstream["session"] = ctx.session
            try:
                return await g.call_tool(params.name, params.arguments or {})
            except ToolPaused as e:
                rep = e.report
                return _error(f"Tool '{rep.name}' is paused by MCP Watchdog: its definition is {rep.status.value} "
                              f"since approval (review priority: {rep.priority.label}). "
                              "A developer must review and approve it before it can be used.")
            except KeyError:
                return _error(f"Unknown tool '{params.name}'.")

        server = Server("mcp-watchdog", on_list_tools=on_list_tools, on_call_tool=on_call_tool)

        async def watch_upstream() -> None:
            while True:
                await g.wait_for_change(timeout=None)
                await notify_host()

        async def watch_store() -> None:
            def stamp():
                try:
                    st = store.path.stat()
                    return (st.st_mtime_ns, st.st_size)
                except FileNotFoundError:
                    return None
            last = stamp()
            while True:
                await anyio.sleep(poll_seconds)
                now = stamp()
                if now != last:
                    last = now
                    store.reload()
                    on_report(g.gate.update(list(g.gate.current.values())), "approvals changed on disk")
                    await notify_host()

        async with stdio_server() as (read, write):
            async with anyio.create_task_group() as tg:
                tg.start_soon(watch_upstream)
                tg.start_soon(watch_store)
                await server.run(read, write, server.create_initialization_options(NotificationOptions(tools_changed=True)))
                tg.cancel_scope.cancel()
