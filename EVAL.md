# Evaluation method and measured evidence

The eligible universe has 411,160 unique companies and matches both hashes in the official contract. Seed 20260913 shuffles the frozen universe into disjoint local splits: 1,000 scale-test companies (`data/entry-companies.jsonl`), 20 development, 20 validation and a 100-company holdout (`data/live-100.jsonl`, used as the smoke test). These are local splits, not Builderr's official batch.

The committed 100-company smoke test (`docs/smoke-test/`) was rerun on commit `62e36cc` after the review fixes: same 100 inputs, 100/100 terminal envelopes, 803 requests, 144 s, $0, integrity audit passed, external coverage unchanged (7 verified websites). The table below is the earlier `168f3ca` measurement.

## November 6 measurements (commit `c39fb1e`, live registry, Windows 11, 8 registry + 24 website workers)

These were run on the revision described in `docs/NOV2026_CHANGE_PLAN.md`, on the same 100 smoke-test inputs as October, plus a new 300-company local holdout (`docs/smoke-test/holdout-300-input.jsonl`). The holdout is not the organiser's 300. Reports are in `docs/smoke-test/nov2026-*`.

| Measure | Smoke 100 (`aviscope-20261106T124719Z`) | Holdout 300 (`aviscope-20261106T124957Z`) |
|---|---:|---:|
| Terminal envelopes / inputs | 100 / 100 | 300 / 300 |
| Failed inputs | 0 | 0 |
| Unfinished at deadline (baseline / enrichment) | 0 / 0 | 0 / 0 |
| Legal identity | 100 | 300 |
| Financials / financial history | 100 / 100 | 300 / 300 |
| Leadership | 99 | 299 |
| Locations | 99 | 298 |
| Group | 7 | 18 |
| Website (verified on the page) | 7 | 34 |
| Brand | 7 | 25 |
| Linked company profiles | 4 | 22 |
| Public activity | 1 | 0 |
| Jobs | 0 | 0 |
| Supported claims | 4,326 | 12,601 |
| Requests | 799 | 2,509 |
| Runtime | 144 s | 312 s |
| Peak memory | 127 MB | 321 MB |
| Third-party cost | $0 | $0 |

- Revenue summary on the smoke test: 71 companies get a year-on-year comparison, and 29 get a stated reason instead.
- Website states on the smoke test: 7 verified, 19 ambiguous (ownership not shown on the page), 9 blocked, 65 with no candidate found, 0 failed.
- Website coverage on the smoke test stayed at 7 under the stricter on-page identity rule. They are the same 7 companies as in October, so on this sample all 7 already showed their name or number on the page. The rule's effect on group and parent sites is shown by the tests in `tests/test_external_evidence.py`, not by this sample.
- Integrity audit (`nov2026-smoke-100-integrity.json`): passed, with eligible-universe membership verified. 487 retained snapshots were hash-checked, 4,300 JSON pointers and 26 HTML locators resolved, and 1,900 financial values matched their source.
- Unchanged replay of the retained smoke corpus gave 0 false changes and was idempotent.
- Earlier passes of the same runs on `878a12e`, `c2c0adb` and `6cfc8b3` gave the same counts to within a few requests. Those commits changed only the packager and its tests, plus the run report's interpreter field.
- Tests: 251 passed with 5 subtests on `c39fb1e`.
- The 1,000- and 1,100-input cases were checked only as cardinality fixtures (`tests/test_deadline.py`), not as live runs. The live 1,000-company scale test is the October one, on `168f3ca`.

## October 14 measurements (commit `168f3ca`, live registry, macOS, 8 registry + 24 website workers)

Before/after comparisons use the **same companies** as the September runs.

| Field family | Smoke 100: Sep 14 | Smoke 100: Oct 14 | Scale 1,000: Sep 14 | Scale 1,000: Oct 14 |
|---|---:|---:|---:|---:|
| Legal identity | 100 | 100 | 1,000 | 1,000 |
| Financials | 100 | 100 | 999 | 999 |
| Leadership | 100 | 99 | 999 | 997 |
| Locations | 71 | **99** | 761 | **996** |
| Group | 7 | 7 | 60 | 63 |
| Website (verified) | 0 | **7** | 7 | **80** |
| Brand | 0 | **7** | 3 | **66** |
| Linked company profiles | 0 | **4** | 0 | **47** |
| Public activity | 0 | **1** | 0 | **5** |
| Jobs | 0 | 0 | 0 | 0 |
| Supported claims | 3,250 | 4,377 | 22,689 | 42,194 |
| Requests | 625 | 793 | 5,373 | 8,291 |
| Runtime | 351 s | **142 s** | 1,128 s | **957 s** |

All runs returned exactly one terminal envelope per input, with zero failed inputs and $0 third-party spend. Integrity audits (`reports/smoke-100-integrity.json`, `reports/scale-1000-integrity.json`) passed with eligible-universe membership verified: every retained snapshot hash matches, every JSON pointer resolves (41,910 at scale), every financial value equals its source (18,972), and every HTML locator re-derives its value from the stored page (284). The leadership drop is a genuine registry 404 (no public roles), not a regression. Peak sampled memory at scale was 929 MB; per-company p50/p95 were 22.6 s and 55.0 s, overlapped across workers.

Website evidence tiers at scale (pre-final run, 83 sites): organisation number on a name-spelling domain 21, exact legal name on a name-spelling domain 20, registry homepage with exact legal name 16, registry homepage with organisation number 13, registry domain spelling the name 10, organisation number plus legal name on a redirected domain 3. The final run applies stricter whole-word name matching and foreign-entity abstention (80 sites).

## Manual precision review

Every accepted external claim in the Oct 14 smoke run, and every accepted website and linked profile in the 1,000-company run, was inspected with its evidence span. The review found and fixed these classes before the final runs:

- site-builder footers published as company profiles (`facebook.com/wix`);
- personal pages sharing a surname (`vibekeholtskog` for HOLTSKOG AS): now one profile per platform, best handle wins;
- a personal Facebook page and a loose `om-` route that recorded `books-from-amazon` as the website;
- subpage meta descriptions creating brand conflicts: now one description per profile;
- case-insensitive name substrings (`drag as needed`): legal names must now be whole words with a capitalised suffix;
- a group page naming the Swedish `AB` alongside the Norwegian `AS`: foreign legal suffixes now count as other entities for name-only tiers.

No organizer gold set or independent labels exist. Exact-entity precision, per-field recall and the official score therefore remain **unverified**, not zero and not 100%.

## Tests and reproducibility

211 tests and five subtests pass in the working tree (fresh-clone installation not revalidated for this count). They cover identity tiers and adversarial pages, checksum-valid competing numbers, shared portals, social-handle ownership, one description and one profile per platform, registry section URLs, robots 4xx/5xx semantics, the Host header and IPv4-first connection, input formats and batch sizes, the cited narrative and the auditor's tamper detection. The September coverage (numeric zero/null/units, scope and period, evidence resolution, conflicts, refresh idempotency, exact association, resume, atomic budgets, URL/DNS safety and local API controls) is retained.

Fixed-vs-gap routing on the 20-company development cohort (September) found no claim-count difference, so fixed routing remains the default.
