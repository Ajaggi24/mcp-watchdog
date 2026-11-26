"""Canonical snapshots of MCP tool definitions.

A snapshot is the part of a tool definition the agent (and the model) actually
sees. Two definitions that differ only in JSON key order or in the order of a
schema's `required` list produce the same canonical form and the same hash.

Nothing else is normalized on purpose: whitespace, Unicode (including
zero-width characters and look-alike letters) and casing all count as changes,
because the model reads them.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Fields of an MCP Tool that shape what the model sees or how the client treats it.
TRACKED_FIELDS = ("title", "description", "inputSchema", "outputSchema", "annotations")


def _canonical_value(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: _canonical_value(v, k) for k, v in sorted(value.items())}
    if isinstance(value, list):
        items = [_canonical_value(v) for v in value]
        # `required` is a set in JSON Schema semantics; its order is meaningless.
        if key == "required" and all(isinstance(i, str) for i in items):
            return sorted(set(items))
        return items
    return value


def canonicalize(tool: dict[str, Any]) -> dict[str, Any]:
    """Return the tracked, canonical form of one tool definition (a plain dict)."""
    out: dict[str, Any] = {"name": tool["name"]}
    for field in TRACKED_FIELDS:
        if tool.get(field) is not None:
            out[field] = _canonical_value(tool[field], field)
    return out


def canonical_json(tool: dict[str, Any]) -> str:
    return json.dumps(canonicalize(tool), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(tool: dict[str, Any]) -> str:
    """SHA-256 of the canonical definition. Used as the hash-only baseline too."""
    return hashlib.sha256(canonical_json(tool).encode("utf-8")).hexdigest()


def tool_to_dict(tool: Any) -> dict[str, Any]:
    """Accept an mcp_types.Tool (pydantic) or a plain dict."""
    if isinstance(tool, dict):
        return tool
    return tool.model_dump(by_alias=True, exclude_none=True)
