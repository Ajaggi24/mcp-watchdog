"""Held-out set 2: the blind test for the frozen v2 rules -> bench/cases/heldout2.json

Cases and answer key written by Aryan Jaggi without reading mcpwatchdog/priority.py,
after the v2 rules were frozen (bench/FROZEN_RULES_v2.sha256). No rule or label was
changed after running the evaluation.

Encoding notes (where a case had to be turned into a concrete tool definition):
  * Base tools contain only name, description and inputSchema (no annotations),
    because the cases don't specify annotations.
  * Case 13 (sort order) is expressed in the tool description.
  * Cases 02, 16, 18: the sentences "The maximum stays 100", "All categories are
    drawn from the same approved public catalog" and "The report uses the same
    inputs" describe what did NOT change; they are encoded as unchanged schema,
    not as new description text.
  * Case 20: compact vs. indented JSON parses to the identical definition, so
    before and after are the same object.

Answer key -> label:  High priority = high, Routine review = medium,
                      Low priority = low,  No definition change = none.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

CASES: list[dict] = []


def tool(name, description, properties=None, required=None):
    schema = {"type": "object", "properties": properties or {}}
    if required:
        schema["required"] = required
    return {"name": name, "description": description, "inputSchema": schema}


def case(cid, label, group, rationale, before, after):
    CASES.append({"id": cid, "group": group, "label": label, "rationale": rationale,
                  "before": before, "after": after})


def desc_case(cid, label, group, rationale, name, old, new, properties=None, required=None):
    case(cid, label, group, rationale,
         tool(name, old, copy.deepcopy(properties), required),
         tool(name, new, copy.deepcopy(properties), required))


CITY = {"city": {"type": "string"}}

desc_case("Y01", "low", "cosmetic", "Wording edit.", "get_weather",
          "Return the forecast for the selected city.", "Show the forecast for the selected city.", CITY, ["city"])

b = tool("list_projects", "List projects.", {"limit": {"type": "integer", "default": 20, "maximum": 100}})
a = copy.deepcopy(b); a["inputSchema"]["properties"]["limit"]["default"] = 50
case("Y02", "medium", "interface", "Default page size raised; maximum unchanged.", b, a)

desc_case("Y03", "high", "sensitive", "Expanded access: one workspace -> any workspace in the organization.", "list_notes",
          "Return notes from the current workspace.", "Return notes from any workspace in the organization.")

desc_case("Y04", "medium", "interface", "Reports additional usage data (token totals).", "get_usage_stats",
          "Report request counts by model.", "Report request counts and input/output token totals by model.")

desc_case("Y05", "high", "sensitive", "Prepare-only tool now delivers externally.", "draft_invoice",
          "Prepare an invoice for review.", "Prepare the invoice and deliver it to the saved billing contact.")

b = tool("find_events", "Find events on a date.",
         {"date": {"type": "string", "description": "YYYY-MM-DD"}}, ["date"])
a = tool("find_events", "Find events on a date.",
         {"start_date": {"type": "string", "description": "YYYY-MM-DD"},
          "end_date": {"type": "string", "description": "YYYY-MM-DD"}}, ["start_date", "end_date"])
case("Y06", "medium", "interface", "Single date replaced by required start/end range.", b, a)

desc_case("Y07", "high", "sensitive", "Reversible archive becomes permanent removal.", "archive_task",
          "Move a task to the archive. It can be restored.",
          "Remove the task from both active and archived views. The action is permanent.")

b = {"name": "search_catalog", "description": "Search the product catalog.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}
a = {"name": "search_catalog", "description": "Search the product catalog.",
     "inputSchema": {"required": ["query"], "properties": {"query": {"type": "string"}}, "type": "object"}}
case("Y08", "none", "noop", "Top-level schema keys reordered only.", b, a)

desc_case("Y09", "medium", "interface", "Output timezone changes from local to UTC.", "get_store_hours",
          "Return store hours in the store's local time.", "Return store hours in UTC.")

desc_case("Y10", "high", "sensitive", "Preview-only tool now applies a refund (financial side effect).", "preview_refund",
          "Calculate the refund amount for an order.",
          "Calculate the refund amount and apply it to the original payment method.")

desc_case("Y11", "low", "cosmetic", "Spelling fix.", "find_manual",
          "Search product manuals by keywrod.", "Search product manuals by keyword.")

b = tool("get_ticket", "Get a support ticket.",
         {"ticket_id": {"type": "string", "description": "An ID from the current project."}}, ["ticket_id"])
a = copy.deepcopy(b)
a["inputSchema"]["properties"]["ticket_id"]["description"] = "An ID from any project, including private projects."
case("Y12", "high", "sensitive", "Expanded access to any project, including private ones.", b, a)

desc_case("Y13", "medium", "interface", "Result ordering reversed.", "list_bookmarks",
          "List bookmarks. Results sort by created_at ascending.",
          "List bookmarks. Results sort by created_at descending.")

b = tool("export_contacts", "Export contacts.",
         {"fields": {"type": "array", "items": {"type": "string"}, "default": ["display_name"]}})
a = copy.deepcopy(b)
a["inputSchema"]["properties"]["fields"]["default"] = ["display_name", "personal_email", "mobile_number"]
case("Y14", "high", "sensitive", "Default export now includes personal email and mobile number.", b, a)

desc_case("Y15", "low", "cosmetic", "Prose formatting (paragraph break removed).", "get_release_notes",
          "Return notes for a release.\n\nIncludes bug fixes.", "Return notes for a release. Includes bug fixes.")

b = tool("search_assets", "Search approved public assets.",
         {"category": {"type": "string", "enum": ["images", "videos"]}})
a = copy.deepcopy(b)
a["inputSchema"]["properties"]["category"]["enum"] = ["images", "videos", "documents"]
case("Y16", "medium", "interface", "New category from the same approved public catalog.", b, a)

b = tool("set_profile_visibility", "Set who can see the user's profile.",
         {"visibility": {"type": "string", "enum": ["private", "team", "public"], "default": "team"}})
a = copy.deepcopy(b)
a["inputSchema"]["properties"]["visibility"]["default"] = "public"
case("Y17", "high", "sensitive", "Default visibility widened from team to public.", b, a)

b = tool("format_report", "Format a report.",
         {"format": {"type": "string", "enum": ["pdf", "html"]}})
a = copy.deepcopy(b)
a["inputSchema"]["properties"]["format"]["enum"] = ["pdf", "html", "markdown"]
case("Y18", "medium", "interface", "New output format; same inputs.", b, a)

desc_case("Y19", "high", "sensitive", "Aggregate headcount becomes individual compensation data.", "get_team_summary",
          "Return total headcount per department.",
          "Return an employee roster with individual compensation alongside department headcounts.")

b = tool("lookup_sku", "Look up a product by SKU.", {"sku": {"type": "string"}}, ["sku"])
case("Y20", "none", "noop", "Same schema, serialized compact instead of indented (identical once parsed).",
     b, copy.deepcopy(b))


if __name__ == "__main__":
    out = Path(__file__).with_name("cases") / "heldout2.json"
    out.write_text(json.dumps(CASES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from collections import Counter
    print(f"wrote {len(CASES)} cases to {out}:", dict(Counter(c["label"] for c in CASES)))
