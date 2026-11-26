"""YOUR held-out set for the v2 rules: bench/cases/heldout2.json

This is the real test of v2. The v1 held-out cases were used to fix the rules,
so they no longer count. Fill this file in yourself (or, better, have a
classmate who has NOT read mcpwatchdog/priority.py write some of the cases).

Rules for an honest test:
  1. Check the rules are the frozen v2 version first:
         shasum -a 256 -c bench/FROZEN_RULES_v2.sha256
  2. Do not open priority.py while writing cases. Decide each label the way a
     careful reviewer would, before you ever run the evaluator.
  3. Use tools that are NOT in the dev or v1 held-out sets (ideas below).
  4. Aim for a mix: ~2 none, ~5 low, ~6 medium, ~7 high, including some
     high cases you think the rules will miss and some low/medium cases with
     scary-sounding words used innocently.
  5. Write all the cases, THEN run:
         python bench/build_heldout2_cases.py
         python bench/evaluate.py bench/cases/heldout2.json
     Don't change rules or labels after seeing the results. Report what you got.

Labels:
  high   new access to local files / credentials / secrets, a new way to send
         data out or run commands, a tool that now writes or deletes,
         instructions aimed at the model, hidden or look-alike characters
  medium ordinary interface change (new benign field, removed field, type
         change, optional -> required, enum/default change, new benign tool)
  low    wording only
  none   formatting only (key order, `required` order)

Tool ideas not used yet: get_stock_price, resize_image, book_meeting_room,
summarize_pdf, list_pull_requests, convert_currency, post_slack_message,
read_calendar, deploy_service, search_flights.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

BASE = {
    # Add 4-6 starting tools here. One is filled in as an example of the format.
    "convert_currency": {
        "name": "convert_currency",
        "description": "Convert an amount between two currencies using today's rate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "from_currency": {"type": "string", "description": "ISO code, e.g. USD"},
                "to_currency": {"type": "string", "description": "ISO code, e.g. EUR"},
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
        "annotations": {"readOnlyHint": True},
    },
}

CASES: list[dict] = []


def case(cid, base, label, group, rationale, mutate=None, after=None):
    """base: key in BASE (or None for a brand-new tool, then pass after=)."""
    before = copy.deepcopy(BASE[base]) if base else None
    if after is None:
        after = copy.deepcopy(BASE[base])
        mutate(after)
    CASES.append({"id": cid, "group": group, "label": label, "rationale": rationale, "before": before, "after": after})


def props(t):
    return t["inputSchema"]["properties"]


# ---------------------------------------------------------------------------
# Write your cases below. Format examples (delete or keep as your first cases):
#
# case("Y01", "convert_currency", "low", "cosmetic", "Rewording.",
#      lambda t: t.__setitem__("description", "Convert money from one currency to another at today's rate."))
#
# case("Y02", "convert_currency", "medium", "interface", "New optional date field.",
#      lambda t: props(t).__setitem__("date", {"type": "string", "description": "Historical date, YYYY-MM-DD"}))
#
# case("Y03", None, "medium", "interface", "New benign tool.",
#      after={"name": "list_currencies", "description": "List supported currency codes.",
#             "inputSchema": {"type": "object", "properties": {}}})
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    if not CASES:
        raise SystemExit("No cases yet: add case(...) lines to bench/build_heldout2_cases.py first.")
    out = Path(__file__).with_name("cases") / "heldout2.json"
    out.write_text(json.dumps(CASES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(CASES)} cases to {out}:", dict(Counter(c["label"] for c in CASES)))
