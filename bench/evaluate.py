"""Evaluate review prioritization on a labeled case set.

    python bench/evaluate.py bench/cases/dev.json
    python bench/evaluate.py bench/cases/heldout.json
    python bench/evaluate.py bench/cases/heldout2.json      # your own held-out set
    python bench/evaluate.py <cases.json> <output-dir>      # default output: bench/results/v2

Compares three reviewers of the same tool-definition changes:

  raw hash        SHA-256 of the definition as received (no canonicalization).
                  Flags every byte change, all at equal priority.
  canonical hash  SHA-256 of the canonical definition (what hash-pinning tools
                  such as mcp-scan do). All flagged changes at equal priority.
  watchdog        canonical diff + rule-based priority (high / medium / low).

Writes <output-dir>/<set>.md and <set>.json.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcpwatchdog.diff import diff_tools  # noqa: E402
from mcpwatchdog.priority import Priority, assess_changes, assess_new_tool  # noqa: E402
from mcpwatchdog.snapshot import fingerprint  # noqa: E402

LEVELS = ["none", "low", "medium", "high"]


def raw_hash(tool) -> str:
    return hashlib.sha256(json.dumps(tool, ensure_ascii=False).encode()).hexdigest()


def predict(case) -> tuple[str, str]:
    before, after = case["before"], case["after"]
    if before is None:
        a = assess_new_tool(after)
    else:
        changes = diff_tools(before, after)
        if not changes:
            return "none", "no change after canonicalization"
        a = assess_changes(changes)
    return a.priority.label, a.reason


def expected_hits_at_k(groups: list[tuple[int, int]], k: int) -> float:
    """groups: (size, n_relevant) in rank order, ties inside a group broken at random."""
    hits, left = 0.0, k
    for size, rel in groups:
        if left <= 0:
            break
        take = min(size, left)
        hits += rel * take / size
        left -= take
    return hits


def evaluate(path: Path) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for c in cases:
        pred, reason = predict(c)
        raw_flag = c["before"] is None or raw_hash(c["before"]) != raw_hash(c["after"])
        canon_flag = c["before"] is None or fingerprint(c["before"]) != fingerprint(c["after"])
        rows.append({**{k: c[k] for k in ("id", "group", "label", "rationale")},
                     "pred": pred, "reason": reason, "raw_flag": raw_flag, "canon_flag": canon_flag})

    needs = [r for r in rows if r["label"] != "none"]
    noop = [r for r in rows if r["label"] == "none"]
    high = [r for r in needs if r["label"] == "high"]
    routine = [r for r in needs if r["label"] in ("low", "medium")]

    # Review queue: every case that needs review, ranked by each method.
    k = len(high)
    wd_groups = []
    for lvl in reversed(LEVELS):
        g = [r for r in needs if r["pred"] == lvl]
        if g:
            wd_groups.append((len(g), sum(r["label"] == "high" for r in g)))
    hash_groups = [(len(needs), len(high))]

    confusion = Counter((r["label"], r["pred"]) for r in rows)
    m = {
        "set": path.stem,
        "n_cases": len(rows),
        "labels": dict(Counter(r["label"] for r in rows)),
        "gate": {
            "needs_review_missed_by_watchdog": sum(r["pred"] == "none" for r in needs),
            "needs_review_missed_by_canonical_hash": sum(not r["canon_flag"] for r in needs),
            "needs_review_missed_by_raw_hash": sum(not r["raw_flag"] for r in needs),
            "formatting_only_flagged_raw_hash": sum(r["raw_flag"] for r in noop),
            "formatting_only_flagged_canonical": sum(r["canon_flag"] for r in noop),
            "formatting_only_flagged_watchdog": sum(r["pred"] != "none" for r in noop),
            "n_formatting_only": len(noop),
        },
        "priority": {
            "high_ranked_high": sum(r["pred"] == "high" for r in high),
            "n_high": len(high),
            "routine_ranked_high": sum(r["pred"] == "high" for r in routine),
            "n_routine": len(routine),
            "exact_label_match": sum(r["pred"] == r["label"] for r in rows),
        },
        "queue": {
            "k": k,
            "watchdog_high_in_top_k": round(expected_hits_at_k(wd_groups, k), 2),
            "hash_high_in_top_k_expected": round(expected_hits_at_k(hash_groups, k), 2),
        },
        "confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())},
        "misses": [r for r in high if r["pred"] != "high"],
        "false_urgent": [r for r in routine if r["pred"] == "high"],
        "other_mismatches": [r for r in rows if r["pred"] != r["label"]
                             and r not in high and not (r in routine and r["pred"] == "high")],
        "rows": rows,
    }
    return m


def to_markdown(m: dict) -> str:
    g, p, q = m["gate"], m["priority"], m["queue"]
    L = [f"# Results: `{m['set']}` ({m['n_cases']} cases)", "",
         f"Labels: {', '.join(f'{k} {v}' for k, v in sorted(m['labels'].items()))}", "",
         "## Approval gate (must never weaken)", "",
         "| | raw hash | canonical hash | watchdog |", "|---|---|---|---|",
         f"| Changes that need review but were not flagged | {g['needs_review_missed_by_raw_hash']} | {g['needs_review_missed_by_canonical_hash']} | {g['needs_review_missed_by_watchdog']} |",
         f"| Formatting-only changes flagged (of {g['n_formatting_only']}) | {g['formatting_only_flagged_raw_hash']} | {g['formatting_only_flagged_canonical']} | {g['formatting_only_flagged_watchdog']} |",
         "", "## Prioritization", "",
         f"- **Sensitive changes ranked high: {p['high_ranked_high']} of {p['n_high']}**",
         f"- **Routine changes (low/medium) wrongly ranked high: {p['routine_ranked_high']} of {p['n_routine']}**",
         f"- Exact label match: {p['exact_label_match']} of {m['n_cases']}",
         f"- Review queue, top {q['k']} slots: watchdog puts {q['watchdog_high_in_top_k']} sensitive changes there; "
         f"a hash-only queue (all changes equal, random order) puts {q['hash_high_in_top_k_expected']} there on average.",
         "", "## Confusion (label -> predicted)", "", "| label | none | low | medium | high |", "|---|---|---|---|---|"]
    for a in LEVELS:
        L.append(f"| {a} | " + " | ".join(str(m["confusion"].get(f"{a}->{b}", 0)) for b in LEVELS) + " |")

    def table(title, rows):
        L.extend(["", f"## {title} ({len(rows)})", ""])
        if not rows:
            L.append("None.")
            return
        L.extend(["| id | group | label | predicted | case | watchdog's reason |", "|---|---|---|---|---|---|"])
        for r in rows:
            L.append(f"| {r['id']} | {r['group']} | {r['label']} | {r['pred']} | {r['rationale']} | {r['reason']} |")

    table("Sensitive changes ranked too low", m["misses"])
    table("Routine changes ranked as urgent", m["false_urgent"])
    table("Other label mismatches", m["other_mismatches"])
    table("All cases", m["rows"])
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "bench" / "cases" / "dev.json")
    m = evaluate(path)
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "bench" / "results" / "v2"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{m['set']}.md").write_text(to_markdown(m), encoding="utf-8")
    (out / f"{m['set']}.json").write_text(json.dumps({k: v for k, v in m.items()}, indent=2, ensure_ascii=False), encoding="utf-8")
    p, q, g = m["priority"], m["queue"], m["gate"]
    print(f"[{m['set']}] sensitive ranked high {p['high_ranked_high']}/{p['n_high']} | "
          f"routine ranked high {p['routine_ranked_high']}/{p['n_routine']} | exact {p['exact_label_match']}/{m['n_cases']} | "
          f"top-{q['k']}: watchdog {q['watchdog_high_in_top_k']} vs hash {q['hash_high_in_top_k_expected']} | "
          f"gate misses {g['needs_review_missed_by_watchdog']} | noop flagged raw {g['formatting_only_flagged_raw_hash']}/{g['n_formatting_only']} canon {g['formatting_only_flagged_canonical']}")
    for r in m["misses"] + m["false_urgent"] + m["other_mismatches"]:
        print(f"  {r['id']} label={r['label']} pred={r['pred']}: {r['rationale']} | {r['reason']}")
