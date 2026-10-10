# 07 - Reconciliation of the feature count (512 / 514 / 515)

## Source of truth
The original specification message of 2026-08-31 (found in the local Claude conversation history, `C:\Users\NITROV15\.claude\projects\C--Users-NITROV15-Downloads\`, 44,496 characters). It was read, not modified. `docs/CAHIER_DES_CHARGES.md` states that the original text was lost; that statement is outdated.

## Counts (mechanical, from the original table rows `| N.N.N | name | description |` before "PARTIE 16")
| Measure | Value |
|---|---:|
| Table rows with an `N.N.N` identifier, Parts 1-15 | 514 |
| Unique identifiers | 514 |
| Duplicated identifiers | 0 |
| Gaps inside a numbered sequence (e.g. 3.4.12 -> 3.4.14) | 0 |
| Rows of Parts 16-17 with identifiers | 0 (Part 16 architecture and Part 17 free testers are prose) |
| Table rows that are not feature rows (payment alternatives table) | 5, outside the numbered items |

Per Part: 1=42, 2=35, 3=41, 4=18, 5=47, 6=22, 7=33, 8=32, 9=37, 10=49, 11=34, 12=23, 13=52, 14=33, 15=16 (sum 514).

## 514 versus 512 versus 515
- The data gives **514 unique items**. No evidence was found for 512 or 515 in the source.
- 21 feature *names* appear twice under different identifiers (42 rows): e.g. "Structured logging" 10.3.2 and 13.5.1, "Unit tests" 13.2.1 and 13.3.3, "Organizations" 1.3.1 and 11.1.1. They are distinct identifiers in distinct Parts; whether the author meant them as 11 deliberate repeats (so ~503-512 functionally distinct) is an interpretation, not a fact. No row was removed or renumbered.
- If the owner's figure of 512 comes from another counting rule (e.g. removing two rows), the rule is unknown. **Retained for the audit: 514.**

## Declared statuses (docs/CAHIER_DES_CHARGES.md) in the source CSV
128 done, 18 partial, 2 not started, 366 not listed in tables (tracked in narrative text only). These columns are preserved unchanged in `01-feature-verification.csv` (`declared_status`) and are never overwritten by audit results.

## Code and test references
`code_refs_in_source_csv` and `test_refs_in_source_csv` are counts of files that mention the identifier. They are leads, not proof; they are kept only for traceability.

## Known limits of the reconciliation
- The count relies on the table format of the original message; a feature written outside a table row would be missed.
- `docs/LISTE_514_FONCTIONNALITES_CAHIER_DES_CHARGES.csv` exists only on the branch of PR #23 (not on `main`); `work/source_list_514.csv` is a verbatim copy of that file as pushed.
