# Results: `heldout2` (20 cases)

Labels: high 8, low 3, medium 7, none 2

## Approval gate (must never weaken)

| | raw hash | canonical hash | watchdog |
|---|---|---|---|
| Changes that need review but were not flagged | 0 | 0 | 0 |
| Formatting-only changes flagged (of 2) | 1 | 0 | 0 |

## Prioritization

- **Sensitive changes ranked high: 0 of 8**
- **Routine changes (low/medium) wrongly ranked high: 0 of 10**
- Exact label match: 9 of 20
- Review queue, top 8 slots: watchdog puts 3.0 sensitive changes there; a hash-only queue (all changes equal, random order) puts 3.56 there on average.

## Confusion (label -> predicted)

| label | none | low | medium | high |
|---|---|---|---|---|
| none | 2 | 0 | 0 | 0 |
| low | 0 | 3 | 0 | 0 |
| medium | 0 | 3 | 4 | 0 |
| high | 0 | 6 | 2 | 0 |

## Sensitive changes ranked too low (8)

| id | group | label | predicted | case | watchdog's reason |
|---|---|---|---|---|---|
| Y03 | sensitive | high | low | Expanded access: one workspace -> any workspace in the organization. | wording change in tool description |
| Y05 | sensitive | high | low | Prepare-only tool now delivers externally. | wording change in tool description |
| Y07 | sensitive | high | low | Reversible archive becomes permanent removal. | wording change in tool description |
| Y10 | sensitive | high | low | Preview-only tool now applies a refund (financial side effect). | wording change in tool description |
| Y12 | sensitive | high | low | Expanded access to any project, including private ones. | wording change in field 'ticket_id' description |
| Y14 | sensitive | high | medium | Default export now includes personal email and mobile number. | field 'fields' default changed |
| Y17 | sensitive | high | medium | Default visibility widened from team to public. | field 'visibility' default changed |
| Y19 | sensitive | high | low | Aggregate headcount becomes individual compensation data. | wording change in tool description |

## Routine changes ranked as urgent (0)

None.

## Other label mismatches (3)

| id | group | label | predicted | case | watchdog's reason |
|---|---|---|---|---|---|
| Y04 | interface | medium | low | Reports additional usage data (token totals). | wording change in tool description |
| Y09 | interface | medium | low | Output timezone changes from local to UTC. | wording change in tool description |
| Y13 | interface | medium | low | Result ordering reversed. | wording change in tool description |

## All cases (20)

| id | group | label | predicted | case | watchdog's reason |
|---|---|---|---|---|---|
| Y01 | cosmetic | low | low | Wording edit. | wording change in tool description |
| Y02 | interface | medium | medium | Default page size raised; maximum unchanged. | field 'limit' default changed |
| Y03 | sensitive | high | low | Expanded access: one workspace -> any workspace in the organization. | wording change in tool description |
| Y04 | interface | medium | low | Reports additional usage data (token totals). | wording change in tool description |
| Y05 | sensitive | high | low | Prepare-only tool now delivers externally. | wording change in tool description |
| Y06 | interface | medium | medium | Single date replaced by required start/end range. | input field 'date' removed; new input field 'end_date'; new input field 'start_date' |
| Y07 | sensitive | high | low | Reversible archive becomes permanent removal. | wording change in tool description |
| Y08 | noop | none | none | Top-level schema keys reordered only. | no change after canonicalization |
| Y09 | interface | medium | low | Output timezone changes from local to UTC. | wording change in tool description |
| Y10 | sensitive | high | low | Preview-only tool now applies a refund (financial side effect). | wording change in tool description |
| Y11 | cosmetic | low | low | Spelling fix. | wording change in tool description |
| Y12 | sensitive | high | low | Expanded access to any project, including private ones. | wording change in field 'ticket_id' description |
| Y13 | interface | medium | low | Result ordering reversed. | wording change in tool description |
| Y14 | sensitive | high | medium | Default export now includes personal email and mobile number. | field 'fields' default changed |
| Y15 | cosmetic | low | low | Prose formatting (paragraph break removed). | wording change in tool description |
| Y16 | interface | medium | medium | New category from the same approved public catalog. | field 'category' enum changed |
| Y17 | sensitive | high | medium | Default visibility widened from team to public. | field 'visibility' default changed |
| Y18 | interface | medium | medium | New output format; same inputs. | field 'format' enum changed |
| Y19 | sensitive | high | low | Aggregate headcount becomes individual compensation data. | wording change in tool description |
| Y20 | noop | none | none | Same schema, serialized compact instead of indented (identical once parsed). | no change after canonicalization |
