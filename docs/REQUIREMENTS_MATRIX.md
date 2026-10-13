# Requirements matrix

Binding sources were rechecked 2026-09-14. Exact UTC times, final URLs and document SHA-256 values are in `requirements/provenance.json`. The current v2 dated contract controls; older starter scoring and organizer-only npm scripts are not local qualification checks.

| ID / requirement | Implementation | Verification / delivery | Status |
|---|---|---|---|
| R01 unfamiliar Norwegian IDs, correct legal identity | `models.org_number`, `pipeline.baseline`, frozen/live registry adapter | invalid-ID/frozen-source tests; real holdout | Implemented; live data mode declared |
| R02 1,000 eligible genuinely researched profiles and exact manifest | seeded `scripts/prepare_data.py`, runner | `data/entry-companies.jsonl`, packaged run/integrity report | Final measured count in manifest; partial profiles disclosed |
| R03 one terminal per input; 100 daily | runner two-phase scheduler, exceptions and checkpoint | cardinality/order/zero-budget/resume tests, live-100 report | Implemented |
| R04 all required field families and six states | Pydantic profile/envelope adapter | schemas, availability map, data profiles | Families present; company-owned external research enabled by default (`SOURCE_RIGHTS.md`), but a live 100-company sample found few registry-listed websites and no candidate yet passing the identity gate — external coverage at full-corpus scale is unmeasured until `out/submission` completes |
| R05 accurate accounts, zero/null, periods/currency/scope | exact JSON paths, numeric-value validation | financial source equality audit, regression tests | Implemented; PDF history disabled |
| R06 claims with dated resolvable evidence | immutable raw/redacted snapshots, original/retained hashes, receipts | `data/evidence`, source manifest, audit | Implemented |
| R07 exact external entity, parent/franchise/group handling | strict deterministic gate, ledger/relationships | adversarial regressions, review queue | Implemented gate; live-100 run observed it correctly quarantine shared-portal and group/SPV candidates rather than publish them; independent precision review still pending |
| R08 source rights, safe outbound URLs, server-side secrets | source policy, DNS-pinned broker, loopback API | source/URL/DNS/API tests, rights/security declarations | Official path enabled; company-owned sites enabled by default per fetched source policy (only named third-party platforms remain hard-disabled) |
| R09 <=2,000 requests, <=45 min, <=$10 per 100 | atomic reservation, journal, bounded retries/redirects, deadline | `reports/live-100-report.json` and budget checks | Free path; measured final report required |
| R10 8 vCPU /16GB RAM /10GB temp | <=8 workers, bounded responses/bytes, streaming outputs and memory sampling | resource report | Local hardware measurement, not organizer execution |
| R11 history, real changes, failed refresh retains values, idempotency | semantic keys, before/after evidence, stale retention | refresh bundle; unchanged live corpus and labelled changed/failed fixtures | Implemented; confirmed deletions unsupported |
| R12 useful grounded synthesis | deterministic supported undisputed claims + unknowns | profile/API/UI checks | Implemented; no LLM |
| R13 find/compare/verify desktop/mobile | explorer/profile/changes/runs interface | browser journeys; screenshots | Locally tested; no public deployment |
| R14 pinned reproducible evaluator and exact frozen revision | `.python-version`, `uv.lock`, one CLI, Git export | fresh extracted package smoke/setup | Packager enforces source/data association |
| R15 submitted hash retrievable and source access | Git origin and local commit; prepared access plan | manifest/checklist/email | Remote push/access pending |
| R16 official email fields | packager-generated TXT/EML and manifest | package email drafts | Unsent; contact/manifest URL/access pending |
| R17 >=65 score, >=21 coverage, >=60% recall, >=95% exact precision | cannot establish from own data | independent review queue; organizer review required | Not determined; no local qualification claim |
| R18 refresh/code freeze, no hidden-label tuning | frozen settings/code/policy hashes | run settings/checkpoint | Implemented |
| R19 version limits, dates, shared rules/prizes | `PRIZES_AND_ELIGIBILITY.md` | clarification draft, submitted-version ledger | No versions submitted; five-version, sparse-pool and missed-run rules now documented |
| I01 gap decisions/receipt design/contradictions | source selector, candidate ledger, conflict queue, receipt UI | `AVISCOPE_DESIGN.md`, routing report | Internal design choices; gap not promoted |
| I02 audited ZIP/checksums/unsent email | `scripts/package_submission.py` | ZIP, external checksum, extracted verification report | Delivery format choice, not invented organizer rule |
| O01 JBOX | Disabled | models/prizes docs | Bonus not pursued; access/benefit unverified |

The archive-source licence ambiguity, the unmeasured full-corpus external-coverage rate, and pending independent identity/claim review prevent treating the package as ready for submission. All source and personal access actions remain separate from local implementation and packaging.
