"""Command line: approve, check, review, proxy.

    python -m mcpwatchdog approve --server "python demo_server/server.py demo_server/defs.json"
    python -m mcpwatchdog check   --server "..."     # exit 1 if any tool needs review (CI-friendly)
    python -m mcpwatchdog review  --server "..."     # interactive per-tool approval
    python -m mcpwatchdog check   --server "..." --html review.html   # visual review page
    python -m mcpwatchdog proxy   --server "..."     # sit in front of a real MCP host (Claude Code, Cursor)
"""

from __future__ import annotations

import argparse
import sys

import anyio

from .client import connect
from .gate import ApprovalStore
from .html import render_html
from .proxy import run_proxy
from .render import print_report


async def _run(args: argparse.Namespace) -> int:
    store = ApprovalStore(args.store)
    async with connect(args.server, store, args.server_id) as g:
        report = g.gate.report
        if args.cmd == "approve":
            names = args.tool or list(g.gate.current)
            for name in names:
                g.gate.approve(name)
            print(f"Approved {len(names)} tool(s) for server '{g.gate.server_id}': {', '.join(sorted(names))}")
            return 0

        print_report(report, f"server '{g.gate.server_id}'")
        if args.html:
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(render_html(report, g.gate.server_id))
            print(f"Wrote review page: {args.html}")
        if args.cmd == "check":
            return 0 if report.clean else 1

        # review
        for rep in report.pending:
            answer = input(f"Approve current definition of '{rep.name}'? [y/N] ").strip().lower()
            if answer == "y":
                g.gate.approve(rep.name)
                print(f"  approved {rep.name}")
        return 0 if g.gate.report.clean else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mcpwatchdog", description="Pause MCP tools whose definitions changed after approval.")
    p.add_argument("cmd", choices=["approve", "check", "review", "proxy"])
    p.add_argument("--server", required=True, help="command that starts the stdio MCP server")
    p.add_argument("--server-id", help="key for this server in the approval store (default: server's reported name)")
    p.add_argument("--store", default=".watchdog/approved.json", help="approval store path")
    p.add_argument("--tool", action="append", help="approve only this tool (repeatable)")
    p.add_argument("--html", help="also write a visual review page to this path (check/review/proxy)")
    p.add_argument("--poll", type=float, default=1.0, help="proxy: seconds between approval-store checks")
    args = p.parse_args(argv)
    if args.cmd == "proxy":
        anyio.run(run_proxy, args.server, args.store, args.server_id, args.html or ".watchdog/review.html", args.poll)
        return 0
    return anyio.run(_run, args)


if __name__ == "__main__":
    sys.exit(main())
