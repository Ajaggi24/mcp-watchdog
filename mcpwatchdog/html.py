"""Self-contained HTML review page for a Watchdog report."""

from __future__ import annotations

import difflib
import html
import json
from datetime import datetime, timezone

from .diff import Change, reveal
from .gate import Report, Status
from .priority import _describe

CSS = """
:root{--bg:#0f1115;--panel:#171a21;--line:#262b36;--text:#e6e8ee;--dim:#8b93a7;
--high:#ff5d5d;--med:#f5b942;--low:#4fc3d9;--ok:#4cd08a;--add:#16351f;--del:#3a1a1d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 20px 60px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--dim);margin:0 0 24px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:0 0 16px;overflow:hidden}
.head{display:flex;gap:12px;align-items:center;padding:14px 16px;border-bottom:1px solid var(--line)}
.n{color:var(--dim);font-variant-numeric:tabular-nums}.name{font:600 16px ui-monospace,Menlo,monospace}
.chip{font:700 11px/1 ui-monospace,monospace;letter-spacing:.06em;padding:5px 8px;border-radius:5px;color:#111}
.high{background:var(--high)}.medium{background:var(--med)}.low{background:var(--low)}
.kind{margin-left:auto;color:var(--dim);font-size:13px}.paused{color:var(--high);font-size:13px;font-weight:600}
.why{padding:10px 16px;color:var(--text);border-bottom:1px solid var(--line)}.why b{color:var(--dim);font-weight:500}
table{width:100%;border-collapse:collapse;font:13px/1.5 ui-monospace,Menlo,monospace}
td{padding:8px 16px;vertical-align:top;border-bottom:1px solid var(--line)}tr:last-child td{border-bottom:0}
td.path{width:32%;color:var(--dim);word-break:break-all}
ins{background:var(--add);color:#9df0b8;text-decoration:none;border-radius:3px;padding:0 2px}
del{background:var(--del);color:#ff9c9c;border-radius:3px;padding:0 2px}
.prio{font-size:11px;color:var(--dim);display:block;margin-top:2px}
.ok{color:var(--ok)}.foot{color:var(--dim);font-size:13px;margin-top:28px}
.approved{padding:12px 16px;font:14px ui-monospace,monospace}
"""


def _esc(s: str) -> str:
    return html.escape(reveal(s))


def _inline_diff(old: str, new: str) -> str:
    a, b = old.split(" "), new.split(" ")
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(_esc(" ".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(f"<del>{_esc(' '.join(a[i1:i2]))}</del>")
            if j2 > j1:
                out.append(f"<ins>{_esc(' '.join(b[j1:j2]))}</ins>")
    return " ".join(x for x in out if x)


def _val(v) -> str:
    return _esc(v if isinstance(v, str) else json.dumps(v, sort_keys=True, ensure_ascii=False))


def _change_cell(ch: Change) -> str:
    if ch.kind == "added":
        return f"<ins>+ {_val(ch.new)}</ins>"
    if ch.kind == "removed":
        return f"<del>- {_val(ch.old)}</del>"
    if isinstance(ch.old, str) and isinstance(ch.new, str):
        return _inline_diff(ch.old, ch.new)
    return f"<del>{_val(ch.old)}</del> → <ins>{_val(ch.new)}</ins>"


def render_html(report: Report, server_id: str = "", title: str = "MCP Watchdog review") -> str:
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    queue = report.pending
    parts = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>",
             f"<h1>{html.escape(title)}</h1>",
             f"<p class='sub'>Server <b>{html.escape(server_id)}</b> · {when} · "
             f"{len(queue)} tool(s) awaiting review, most urgent first. Calls to these tools are paused until approved.</p>"]
    for i, rep in enumerate(queue, 1):
        p = rep.priority.label
        kind = "new tool" if rep.status is Status.NEW else f"{len(rep.changes)} field change(s)"
        parts.append(f"<section class='card'><div class='head'><span class='n'>{i}</span>"
                     f"<span class='chip {p}'>{p.upper()}</span><span class='name'>{html.escape(rep.name)}</span>"
                     f"<span class='paused'>⏸ paused</span><span class='kind'>{kind}</span></div>"
                     f"<div class='why'><b>Why this priority:</b> {html.escape(rep.assessment.reason)}</div>")
        if rep.changes:
            by_path: dict[str, list] = {}
            for f in rep.assessment.findings:
                by_path.setdefault(f.path, []).append(f)
            parts.append("<table>")
            for ch in rep.changes:
                where = _describe(ch.path)
                fs = [f for path, lst in by_path.items() for f in lst
                      if path and (path == where or ch.path.startswith(path) or path.startswith(ch.path))]
                top = max(fs, key=lambda f: f.priority) if fs else None
                note = f"<span class='prio'>{html.escape(top.priority.label)}: {html.escape(top.reason)}</span>" if top else ""
                parts.append(f"<tr><td class='path'>{html.escape(ch.path)}{note}</td><td>{_change_cell(ch)}</td></tr>")
            parts.append("</table>")
        parts.append("</section>")
    ok = sorted(n for n, r in report.tools.items() if not r.needs_review)
    if ok:
        parts.append("<section class='card'><div class='approved'>" +
                     " · ".join(f"<span class='ok'>✓</span> {html.escape(n)}" for n in ok) +
                     " <span style='color:var(--dim)'>— unchanged since approval</span></div></section>")
    if report.removed:
        parts.append(f"<p class='sub'>Removed by server: {html.escape(', '.join(report.removed))}</p>")
    parts.append("<p class='foot'>Priority only orders the queue. Every changed or new definition needs explicit approval, "
                 "whatever its priority. Watchdog compares tool definitions only; it cannot see a server's runtime behavior.</p>"
                 "</main></body></html>")
    return "".join(parts)
