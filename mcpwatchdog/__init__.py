"""MCP Watchdog: pause MCP tools whose definitions changed after you approved them."""

from .diff import Change, diff_tools
from .gate import ApprovalStore, Gate, Report, Status, ToolPaused, evaluate
from .snapshot import canonicalize, fingerprint

__all__ = [
    "ApprovalStore", "Change", "Gate", "Report", "Status", "ToolPaused",
    "canonicalize", "diff_tools", "evaluate", "fingerprint",
]
