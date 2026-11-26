# GitHub issues and release notes for MCP Watchdog

Paste each block into GitHub. Do the releases after you've pushed both patches.

---

## Releases

### Release `v1.0` (tag on commit `e2690e4`)

**Title:** v1.0: first evaluated version

**Notes:**

First version of MCP Watchdog: snapshot, field-level diff, review priority and call gate for MCP tool definitions.

**Evaluation (rules frozen before the held-out cases were written):**
- 22 held-out tool changes on 6 tools not used during development
- Sensitive changes ranked high: 7 of 9
- Routine changes wrongly ranked urgent: 2 of 11
- Changes that skipped review: 0
- Sensitive changes in the top 9 of the review queue: 7, vs. 4.05 expected for a hash-only alert

**Known failures:** a read-only database tool gaining UPDATE/DELETE (described only in prose), an instruction hidden in an HTML comment, "tokens" (LLM tokens) flagged as a secret, a benign `filename` field flagged as file access, and accented letters treated as look-alike characters. Details in RESULTS.md.

### Release `v2.0` (tag on your v2 commit)

**Title:** v2.0: fixes for the v1 held-out failures

**Notes:**

Fixes all five v1 held-out failures with no regressions on the 40 dev cases:
- Write/delete capability described in prose is now high priority
- HTML comments and text addressed to the model are treated as hidden instructions
- Only qualified tokens (API, access, auth, …) count as secrets
- Weak field names (`file`, `path`, `key`, …) escalate only when the field also points at local files
- Look-alike detection limited to scripts that imitate Latin; email addresses in prose flagged as outside destinations

**Important:** v2 has not yet been evaluated on unseen cases. The v1 held-out set was used to make these fixes, so it no longer counts as a test. The v2 rules are hash-frozen (`bench/FROZEN_RULES_v2.sha256`) pending a new blind evaluation (see the "Blind evaluation of v2" issue).

### Release `v2.1` (tag after the proxy patch, optional)

**Title:** v2.1: proxy mode and CI

**Notes:**
- `mcpwatchdog proxy` runs Watchdog in front of real MCP hosts such as Claude Code and Cursor. Unapproved tools are withheld from the host entirely, so the model never reads their descriptions. Approvals take effect live, without restarting the host.
- GitHub Actions runs the tests, the frozen-rule hash check and the gate-integrity check on Python 3.10, 3.12 and 3.13 on every push.
- Rules unchanged from v2.0.

**Tag commands** (replace `<v2-commit>` and `<proxy-commit>` with hashes from `git log --oneline`):
```bash
git tag -a v1.0 e2690e4 -m "v1.0: first evaluated version"
git tag -a v2.0 <v2-commit> -m "v2.0: fixes for the v1 held-out failures"
git tag -a v2.1 <proxy-commit> -m "v2.1: proxy mode and CI"
git push --tags
```
Then go to the repo page → Releases → Draft a new release, choose each tag, and paste the notes above.

---

## Issues

### Issue 1: Blind evaluation of v2 on a new held-out set

**Labels:** evaluation

The v2 rules fix the five v1 held-out failures, but those cases were used to make the fixes, so v2 has no unseen-case result yet.

**Plan**
- [ ] Write ~20 new labeled cases in `bench/build_heldout2_cases.py` on tools not used in dev or v1 held-out
- [ ] Have at least some cases written by someone who hasn't read `priority.py`
- [ ] Confirm `shasum -a 256 -c bench/FROZEN_RULES_v2.sha256` passes before running
- [ ] Run `bench/evaluate.py bench/cases/heldout2.json` and publish the results in RESULTS.md, whatever they are

**Done when:** RESULTS.md reports v2's held-out numbers next to v1's.

---

### Issue 2: Compare an LLM-based classifier against the rules

**Labels:** enhancement, evaluation

Keyword rules missed changes where the risk was only in plain language (v1 H14, H21). Test whether an LLM classifier ranks changes better.

**Plan**
- [ ] Classifier that takes (before, after, diff) and returns high/medium/low plus a reason
- [ ] Evaluate on the same held-out sets as the rules, reporting the same metrics
- [ ] Report cost and latency per change
- [ ] Check robustness: the changed description could itself contain instructions aimed at the classifier

**Done when:** RESULTS.md has a rules vs. LLM comparison on unseen cases.

---

### Issue 3: Reduce false alarms from the v2 write/delete rule

**Labels:** enhancement

v2 flags new text containing words like `update` or `delete` as high priority. That's likely to fire on harmless edits to tools that could always update or delete (e.g. rewording the description of a `delete_note` tool).

**Ideas**
- Only escalate when the approved definition had no write capability (no write words, `readOnlyHint: true`)
- Weigh the tool name and annotations together with the prose

**Done when:** new held-out cases covering this pattern are added and the false-alarm rate is reported. Don't tune on the blind set.

---

### Issue 4: Test proxy mode with Claude Code and Cursor

**Labels:** testing

The proxy is covered by an automated end-to-end test with a plain MCP client. It still needs a manual check with real hosts.

**Plan**
- [ ] Claude Code: add the proxy with `claude mcp add`, approve, change the server's tools mid-session, and confirm the tool disappears and comes back after `review`
- [ ] Cursor: same, using `.cursor/mcp.json`
- [ ] Note in the README any host-specific behavior (e.g. whether the host re-lists tools on `list_changed`)

---

### Issue 5: Support HTTP MCP servers

**Labels:** enhancement

Watchdog currently connects to upstream servers over stdio only. Many hosted MCP servers use streamable HTTP.

**Plan**
- [ ] `--url` option for an HTTP upstream in `connect()` and the proxy
- [ ] End-to-end test against a local HTTP demo server
