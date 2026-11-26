"""Field-level diffs between an approved tool definition and the current one."""

from __future__ import annotations

import difflib
import json
import unicodedata
from dataclasses import dataclass
from typing import Any

from .snapshot import canonicalize

_MISSING = object()


@dataclass(frozen=True)
class Change:
    path: str          # e.g. "inputSchema.properties.file_path"
    kind: str          # "added" | "removed" | "changed"
    old: Any = None
    new: Any = None

    def summary(self) -> str:
        if self.kind == "added":
            return f"+ {self.path} = {show(self.new)}"
        if self.kind == "removed":
            return f"- {self.path} (was {show(self.old)})"
        if isinstance(self.old, str) and isinstance(self.new, str):
            return f"~ {self.path}: {word_diff(self.old, self.new)}"
        return f"~ {self.path}: {show(self.old)} -> {show(self.new)}"


def reveal(text: str) -> str:
    """Make invisible or confusable characters visible, e.g. zero-width spaces."""
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch in "\n\t":
            out.append({"\n": "\\n", "\t": "\\t"}[ch])
        elif cat in ("Cf", "Cc", "Zl", "Zp") or (cat == "Zs" and ch != " "):
            out.append(f"<U+{ord(ch):04X}>")
        elif ord(ch) > 127 and cat.startswith("L"):
            out.append(f"{ch}<U+{ord(ch):04X}>")
        else:
            out.append(ch)
    return "".join(out)


def show(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(reveal(value), ensure_ascii=False)
    return reveal(json.dumps(value, sort_keys=True, ensure_ascii=False))


def word_diff(old: str, new: str) -> str:
    """Inline diff: [-removed-] {+added+}."""
    a, b = old.split(" "), new.split(" ")
    parts: list[str] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            parts.append(" ".join(a[i1:i2]))
        else:
            if i2 > i1:
                parts.append("[-" + reveal(" ".join(a[i1:i2])) + "-]")
            if j2 > j1:
                parts.append("{+" + reveal(" ".join(b[j1:j2])) + "+}")
    return " ".join(p for p in parts if p)


def _walk(old: Any, new: Any, path: str, out: list[Change]) -> None:
    if old is _MISSING:
        out.append(Change(path, "added", new=new))
        return
    if new is _MISSING:
        out.append(Change(path, "removed", old=old))
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            _walk(old.get(key, _MISSING), new.get(key, _MISSING), f"{path}.{key}" if path else key, out)
        return
    if path.endswith("required") and isinstance(old, list) and isinstance(new, list):
        for name in sorted(set(new) - set(old)):
            out.append(Change(f"{path}[{name}]", "added", new=name))
        for name in sorted(set(old) - set(new)):
            out.append(Change(f"{path}[{name}]", "removed", old=name))
        return
    if old != new:
        out.append(Change(path, "changed", old=old, new=new))


def diff_tools(approved: dict[str, Any], current: dict[str, Any]) -> list[Change]:
    """All field-level changes from the approved definition to the current one.

    An empty list means the definitions are equivalent after canonicalization
    (for example, only JSON key order changed).
    """
    a, b = canonicalize(approved), canonicalize(current)
    out: list[Change] = []
    _walk(a, b, "", out)
    return out
