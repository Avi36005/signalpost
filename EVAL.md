# Evaluation method and measured evidence

The eligible universe has 411,160 unique companies and matches both hashes in the current official contract. Seed 20260913 shuffles the frozen universe, selecting 1,000 entry companies, 20 development companies, 20 validation companies and 100 operational holdout companies with no organisation overlap. Smoke is the first ten entry rows. Group/host overlap is not independently established; these are local splits, not Builderr's hidden set.

Pilot: ten live companies yielded ten researched partial profiles, 225 supported claims, 50 requests, 14.063 seconds and $0 API cost. The integrity audit resolved 225 JSON claim locators and checked 67 financial values against their retained numeric source values. This tests traceability, not independent semantic truth.

Regression suite after the Windows portability fix and the company-owned-site policy change: 153 tests and five subtests passed. Tests cover strict identity failures, numeric zero/null/units, scope/period distinction, evidence resolution, conflicts, idempotent/changed/failed refresh, exact output association, resume, atomic request budgets, retry/redirect accounting, source permissions, unsafe DNS/URLs and local API controls. Source code changes require affected checks to run again; final XML is packaged under reports.

The representative live-100 and final corpus reports carry actual command, code hash/commit, environment, input/lock hashes, requests, runtime, peak sampled memory, output-disk footprint, per-company p50/p95 timing and API cost. The CPU concurrency is bounded at eight; these measurements do not simulate an evaluator hardware quota. Final files take precedence over pilot numbers.

`scripts/evaluate_artifacts.py` records unchanged replay on real retained profiles. Synthetic changed/failed responses remain separate labelled tests. The live UI refresh is another measured real-source run and may correctly produce zero changes.

Routing comparisons use the same disjoint development manifest under fixed versus gap settings, with company-owned external sources enabled. The measured comparison (`reports/evaluation/routing-comparison.json`) found identical supported-claim counts under both orderings on that 20-company cohort, so no live routing benefit is established and gap is not promoted. No official family weights or score are invented.

Independent human labels are absent. A per-company review queue is emitted. Exact-entity precision, per-field precision/recall, wrong-company publication count and official score remain **unverified**, not zero or 100%. Official qualification remains `not_determined`.
