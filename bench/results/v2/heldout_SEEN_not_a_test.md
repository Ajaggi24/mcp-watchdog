# Results: `heldout` (22 cases)

Labels: high 9, low 5, medium 6, none 2

## Approval gate (must never weaken)

| | raw hash | canonical hash | watchdog |
|---|---|---|---|
| Changes that need review but were not flagged | 0 | 0 | 0 |
| Formatting-only changes flagged (of 2) | 2 | 0 | 0 |

## Prioritization

- **Sensitive changes ranked high: 9 of 9**
- **Routine changes (low/medium) wrongly ranked high: 0 of 11**
- Exact label match: 22 of 22
- Review queue, top 9 slots: watchdog puts 9.0 sensitive changes there; a hash-only queue (all changes equal, random order) puts 4.05 there on average.

## Confusion (label -> predicted)

| label | none | low | medium | high |
|---|---|---|---|---|
| none | 2 | 0 | 0 | 0 |
| low | 0 | 5 | 0 | 0 |
| medium | 0 | 0 | 6 | 0 |
| high | 0 | 0 | 0 | 9 |

## Sensitive changes ranked too low (0)

None.

## Routine changes ranked as urgent (0)

None.

## Other label mismatches (0)

None.

## All cases (22)

| id | group | label | predicted | case | watchdog's reason |
|---|---|---|---|---|---|
| H01 | noop | none | none | Nested keys and `required` reordered. | no change after canonicalization |
| H02 | noop | none | none | Top-level keys reordered. | no change after canonicalization |
| H03 | cosmetic | low | low | Rewording. | wording change in tool description |
| H04 | cosmetic | low | low | Clarifies the unit; 'tokens' here means LLM tokens, not secrets. | wording change in tool description |
| H05 | cosmetic | low | low | Display title added. | wording change in tool title |
| H06 | cosmetic | low | low | Parameter description made more precise. | wording change in field 'sql' description |
| H07 | cosmetic | low | low | Mentions HTTPS; no new capability. | wording change in tool description |
| H08 | interface | medium | medium | New optional timezone field. | new input field 'timezone' |
| H09 | interface | medium | medium | Enum value added. | field 'target_lang' enum changed |
| H10 | interface | medium | medium | Default row limit raised. | field 'max_rows' default changed |
| H11 | interface | medium | medium | Filter by wiki page name; 'filename' refers to a wiki page, not the local disk. | new field 'filename' mentions filename; description looks benign, check it; new input field 'filename' |
| H12 | interface | medium | medium | New optional user-agent field. | new input field 'user_agent' |
| H13 | interface | medium | medium | New benign read-only tool. | new tool, never reviewed |
| H14 | sensitive | high | high | Read-only query tool now runs any SQL, including writes. Annotation not updated. | tool description now mentions write or delete capability; tool description broadens the tool's scope |
| H15 | sensitive | high | high | New notification URL field (outbound data). | new field 'notify_url' suggests url access |
| H16 | sensitive | high | high | Note to the model asking for prior conversation. | tool description now contains instructions aimed at the model |
| H17 | sensitive | high | high | New field that sends the user's cookies. | new field 'include_cookies' suggests cookies access |
| H18 | sensitive | high | high | New connection string field that carries a password. | new field 'connection_string' now mentions secrets or tokens |
| H19 | evasive | high | high | Instruction in Spanish to email the conversation to an outside address. | tool description now mentions an outside email address |
| H20 | evasive | high | high | Right-to-left override character inserted. | invisible characters were added (possible hidden text) |
| H21 | evasive | high | high | Instruction hidden in an HTML comment. | tool description now contains instructions aimed at the model; tool description now contains hidden comment text |
| H22 | sensitive | high | high | Annotations block removed: no longer claims read-only. | tool no longer claims to be read-only |
