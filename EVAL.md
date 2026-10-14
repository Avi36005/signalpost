# Evaluation method and measured evidence

The eligible universe has 411,160 unique companies and matches both hashes in the official contract. Seed 20260913 shuffles the frozen universe into disjoint local splits: 1,000 scale-test companies (`data/entry-companies.jsonl`), 20 development, 20 validation and a 100-company holdout (`data/live-100.jsonl`, used as the smoke test). These are local splits, not Builderr's official batch.

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

189 tests and five subtests pass, in the working tree and in a fresh clone installed only with `uv sync --frozen`. They cover identity tiers and adversarial pages, checksum-valid competing numbers, shared portals, social-handle ownership, one description and one profile per platform, registry section URLs, robots 4xx/5xx semantics, the Host header and IPv4-first connection, input formats and batch sizes, the cited narrative and the auditor's tamper detection. The September coverage (numeric zero/null/units, scope and period, evidence resolution, conflicts, refresh idempotency, exact association, resume, atomic budgets, URL/DNS safety and local API controls) is retained.

Fixed-vs-gap routing on the 20-company development cohort (September) found no claim-count difference, so fixed routing remains the default.
