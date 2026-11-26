"""Terminal output for reports. Plain ANSI, no dependencies."""

from __future__ import annotations

import os
import sys

from .gate import Report, Status
from .priority import Priority

_COLOR = sys.stdout.isatty() or bool(os.environ.get("FORCE_COLOR"))
if os.environ.get("NO_COLOR"):
    _COLOR = False


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


RED, GREEN, YELLOW, BLUE, DIM, BOLD = "31", "32", "33", "36", "2", "1"
_PRIO_COLOR = {Priority.HIGH: "1;31", Priority.MEDIUM: "33", Priority.LOW: "36", Priority.NONE: "2"}


def render_report(report: Report, reason: str = "") -> str:
    head = f"── Watchdog check: {reason} ──" if reason else "── Watchdog check ──"
    lines = [c(head, DIM)]
    queue = report.pending
    if queue:
        lines.append(c(f"  Review queue ({len(queue)}) - calls to these tools are paused:", BOLD))
        for i, rep in enumerate(queue, 1):
            prio = rep.priority
            tag = c(f"[{prio.label.upper()}]", _PRIO_COLOR[prio]) + " " * (6 - len(prio.label))
            kind = "NEW TOOL" if rep.status is Status.NEW else f"CHANGED, {len(rep.changes)} field(s)"
            lines.append(f"  {i}. {tag} {c(rep.name, BOLD)}  ({kind})")
            lines.append(f"       why: {rep.assessment.reason}")
            for ch in rep.changes:
                lines.append(c(f"       {ch.summary()}", DIM if prio < Priority.HIGH else "0"))
    for name in sorted(n for n, r in report.tools.items() if not r.needs_review):
        lines.append(f"  {c('✓', GREEN)} {name:<14} {c('approved', GREEN)}")
    for name in report.removed:
        lines.append(f"  {c('-', DIM)} {name:<14} {c('removed by server', DIM)}")
    if report.clean:
        lines.append(c("  No review needed.", GREEN))
    return "\n".join(lines)


def print_report(report: Report, reason: str = "") -> None:
    print(render_report(report, reason), flush=True)
