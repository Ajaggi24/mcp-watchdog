"""Review priority for changed or new tools, with a plain-English reason.

Priority only orders the review queue. It never approves anything: every
changed or new definition stays paused until a developer approves it.

Rules are deliberately simple and explainable. Each rule looks only at what
was *added or changed*, so text that was already in an approved definition
does not raise the priority again.

  high    sensitive field names, sensitive text (credentials, local paths,
          shell commands, outbound URLs), instruction-like text aimed at the
          model, scope-broadening wording, safety-annotation escalation,
          new outbound defaults, invisible or look-alike characters,
          encoded blobs
  medium  any other schema change (fields, types, required, enum, default,
          output schema) and new tools with no sensitive signal
  low     wording-only changes to descriptions or titles
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from .diff import Change


class Priority(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Finding:
    priority: Priority
    reason: str
    path: str = ""


@dataclass
class Assessment:
    priority: Priority = Priority.NONE
    findings: list[Finding] = field(default_factory=list)

    def add(self, f: Finding) -> None:
        self.findings.append(f)
        self.priority = max(self.priority, f.priority)

    @property
    def reason(self) -> str:
        top: list[str] = []
        for f in self.findings:
            if f.priority == self.priority and f.reason not in top:
                top.append(f.reason)
        return "; ".join(top[:3])


# ---------------------------------------------------------------- vocab
SENSITIVE_NAME_TOKENS = {
    "file", "filepath", "filename", "path", "dir", "directory", "folder",
    "credential", "credentials", "secret", "secrets", "token", "password", "passwd",
    "apikey", "key", "ssh", "cookie", "cookies", "session", "env",
    "command", "cmd", "shell", "exec", "script", "eval",
    "url", "uri", "webhook", "callback", "endpoint", "bcc", "forward", "upload",
}

SENSITIVE_TEXT = [
    (r"~/|/etc/|/home/|/users/|\bc:\\", "a local filesystem path"),
    (r"\.ssh\b|\bssh keys?\b|\bid_rsa\b|\bid_ed25519\b", "SSH keys"),
    (r"\.aws\b|\bcredentials?\b|\.kube\b|kubeconfig", "credentials"),
    (r"\.env\b|\benvironment variables?\b", "environment secrets"),
    (r"\bpasswords?\b|\bapi[ _-]?keys?\b|\bsecrets?\b|\bprivate keys?\b|\b(access|auth|bearer|personal) tokens?\b|\btokens?\b",
     "secrets or tokens"),
    (r"\bshell\b|\bbash\b|\bexecute\b|\brun (a |the )?(shell )?commands?\b|\bstdout\b", "command execution"),
    (r"https?://|\bpost (it|them|the result|results)\b|\bsend (it|them|this|the result|results) to\b|\bupload\b",
     "sending data to an outside endpoint"),
    (r"\bcontents of\b|\bbash_history\b|\bshell history\b", "reading local file contents"),
]

INSTRUCTION_TEXT = [
    r"<\s*important\s*>", r"\bignore (all|any|the)? ?(previous|prior|above)\b",
    r"\bdo not (tell|mention|inform|show|reveal)\b", r"\bwithout (telling|informing|asking)\b",
    r"\bbefore (using|calling|searching|reading|you)\b", r"\balways (append|include|pass|send|read|attach|add)\b",
    r"\byou must\b", r"\balso (pass|include|send|read|attach)\b", r"\bfirst (read|call|run|fetch)\b",
]

SCOPE_TEXT = [
    r"\bany (file|files|document|documents|path|folder|domain|address|recipient|url)\b",
    r"\bon (this|the) (machine|host|computer|disk|system)\b", r"\banywhere\b",
    r"\b(outside|external|any) domains?\b", r"\ball files\b",
]

_TEXT_KEYS = ("description", "title")
_BLOB = re.compile(r"\b[A-Za-z0-9+/]{20,}={0,2}")
_EMAIL_OR_URL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|https?://", re.I)


# ---------------------------------------------------------------- helpers
def _name_tokens(name: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    parts = [p.lower() for p in re.split(r"[\s_\-.]+", spaced) if p]
    joined = "".join(parts)
    return set(parts) | {joined}


def _strings(value: Any) -> list[str]:
    """All strings in a value, including dict keys (property names)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for k, v in value.items():
            out.append(k)
            out.extend(_strings(v))
        return out
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def _added_text(old: str, new: str) -> str:
    """Words present in `new` that were not in `old` (a cheap, order-insensitive approximation)."""
    old_words = set(old.split())
    return " ".join(w for w in new.split() if w not in old_words)


def _obfuscation(old: str, new: str) -> str | None:
    def invisible(s: str) -> set[str]:
        return {ch for ch in s if unicodedata.category(ch) in ("Cf", "Co", "Cs")}

    def lookalike(s: str) -> set[str]:
        out = set()
        for word in re.findall(r"\w+", s):
            letters = [ch for ch in word if ch.isalpha()]
            if any(ord(ch) < 128 for ch in letters) and any(ord(ch) >= 128 for ch in letters):
                out |= {ch for ch in letters if ord(ch) >= 128}
        return out

    if invisible(new) - invisible(old):
        return "invisible characters were added (possible hidden text)"
    if lookalike(new) - lookalike(old):
        return "look-alike non-Latin letters mixed into words"
    return None


def _scan_text(text: str, where: str, a: Assessment) -> None:
    low = text.lower()
    for pattern, what in SENSITIVE_TEXT:
        if re.search(pattern, low):
            a.add(Finding(Priority.HIGH, f"{where} now mentions {what}", where))
            break
    for pattern in INSTRUCTION_TEXT:
        if re.search(pattern, low):
            a.add(Finding(Priority.HIGH, f"{where} now contains instructions aimed at the model", where))
            break
    for pattern in SCOPE_TEXT:
        if re.search(pattern, low):
            a.add(Finding(Priority.HIGH, f"{where} broadens the tool's scope", where))
            break
    for blob in _BLOB.findall(text):
        if re.search(r"[a-z]", blob) and re.search(r"[A-Z]", blob) and re.search(r"\d", blob):
            a.add(Finding(Priority.HIGH, f"{where} now contains an encoded blob", where))
            break


def _scan_new_property(name: str, schema: Any, path: str, a: Assessment) -> None:
    hits = _name_tokens(name) & SENSITIVE_NAME_TOKENS
    if hits:
        a.add(Finding(Priority.HIGH, f"new field '{name}' suggests {sorted(hits)[0]} access", path))
    for s in _strings(schema):
        _scan_text(s, f"new field '{name}'", a)
    if isinstance(schema, dict) and isinstance(schema.get("default"), str) and _EMAIL_OR_URL.search(schema["default"]):
        a.add(Finding(Priority.HIGH, f"new field '{name}' defaults to an outside destination", path))


def _is_text_path(path: str) -> bool:
    return path.split(".")[-1] in _TEXT_KEYS


# ---------------------------------------------------------------- annotations
def _annotation_finding(ch: Change) -> Finding | None:
    key = ch.path.split(".")[-1]
    new = ch.new if ch.kind != "removed" else None
    old = ch.old if ch.kind != "added" else None
    if ch.path == "annotations":
        return None
    if key == "readOnlyHint" and old is True and new is not True:
        return Finding(Priority.HIGH, "tool no longer claims to be read-only", ch.path)
    if key == "destructiveHint" and new is True:
        return Finding(Priority.HIGH, "tool now says it may be destructive", ch.path)
    if key == "openWorldHint" and new is True and old is not True:
        return Finding(Priority.HIGH, "tool now reaches outside systems", ch.path)
    return Finding(Priority.MEDIUM, f"annotation '{key}' changed", ch.path)


# ---------------------------------------------------------------- entry points
def assess_changes(changes: list[Change]) -> Assessment:
    a = Assessment()
    for ch in changes:
        path = ch.path
        if path == "annotations" and ch.kind in ("added", "removed"):
            # whole annotations block added/removed: expand to per-key changes
            block = ch.new if ch.kind == "added" else ch.old
            for k, v in (block or {}).items():
                sub = Change(f"annotations.{k}", ch.kind, old=v if ch.kind == "removed" else None,
                             new=v if ch.kind == "added" else None)
                if (f := _annotation_finding(sub)):
                    a.add(f)
            continue
        if path.startswith("annotations."):
            if (f := _annotation_finding(ch)):
                a.add(f)
            continue

        # obfuscation in any string change
        if isinstance(ch.new, str) and ch.kind == "changed" and isinstance(ch.old, str):
            if (why := _obfuscation(ch.old, ch.new)):
                a.add(Finding(Priority.HIGH, why, path))
        elif ch.kind == "added":
            for s in _strings(ch.new):
                if (why := _obfuscation("", s)):
                    a.add(Finding(Priority.HIGH, why, path))
                    break

        where = _describe(path)
        if _is_text_path(path) and ch.kind == "changed" and isinstance(ch.old, str):
            added = _added_text(ch.old, ch.new)
            _scan_text(added, where, a)
            a.add(Finding(Priority.LOW, f"wording change in {where}", path))
            continue

        m = re.search(r"properties\.([^.]+)$", path)
        if m and ch.kind == "added":
            _scan_new_property(m.group(1), ch.new, path, a)
            a.add(Finding(Priority.MEDIUM, f"new input field '{m.group(1)}'", path))
            continue

        # any other added/changed value: scan its new text, then it's an interface change
        old_strings = set(_strings(ch.old)) if ch.kind == "changed" else set()
        for s in _strings(ch.new):
            if s not in old_strings:
                _scan_text(s, where, a)
        if path.endswith(".default") and isinstance(ch.new, str) and _EMAIL_OR_URL.search(ch.new):
            a.add(Finding(Priority.HIGH, f"{where} now points to an outside destination", path))
        if _is_text_path(path):
            a.add(Finding(Priority.LOW, f"wording change in {where}", path))
        else:
            a.add(Finding(Priority.MEDIUM, _interface_reason(ch), path))
    return a


def assess_new_tool(tool: dict[str, Any]) -> Assessment:
    a = Assessment()
    a.add(Finding(Priority.MEDIUM, "new tool, never reviewed"))
    hits = _name_tokens(tool["name"]) & SENSITIVE_NAME_TOKENS
    if hits:
        a.add(Finding(Priority.HIGH, f"new tool name suggests {sorted(hits)[0]} access", "name"))
    for text in (tool.get("description") or "", tool.get("title") or ""):
        _scan_text(text, "new tool's description", a)
        if (why := _obfuscation("", text)):
            a.add(Finding(Priority.HIGH, why, "description"))
    for name, schema in ((tool.get("inputSchema") or {}).get("properties") or {}).items():
        _scan_new_property(name, schema, f"inputSchema.properties.{name}", a)
    ann = tool.get("annotations") or {}
    if ann.get("destructiveHint") is True:
        a.add(Finding(Priority.HIGH, "new tool says it may be destructive", "annotations.destructiveHint"))
    return a


def _describe(path: str) -> str:
    if path in ("description", "title"):
        return f"tool {path}"
    m = re.match(r"inputSchema\.properties\.([^.]+)\.(.+)$", path)
    if m:
        return f"field '{m.group(1)}' {m.group(2).split('.')[0]}"
    return path


def _interface_reason(ch: Change) -> str:
    p = ch.path
    if m := re.match(r"inputSchema\.required\[(.+)\]$", p):
        return f"field '{m.group(1)}' is now required" if ch.kind == "added" else f"field '{m.group(1)}' is now optional"
    if m := re.match(r"inputSchema\.properties\.([^.]+)$", p):
        return f"input field '{m.group(1)}' removed" if ch.kind == "removed" else f"input field '{m.group(1)}' changed"
    if m := re.match(r"inputSchema\.properties\.([^.]+)\.(type|enum|default|format|pattern)$", p):
        return f"field '{m.group(1)}' {m.group(2)} changed"
    if p.startswith("outputSchema"):
        return "output schema changed"
    return f"schema change at {p}"
