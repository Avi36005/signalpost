# AviScope build status

Started 2026-09-13. Local source branch: main. Repository destination clarification pending; existing origin is Avi36005/builderr-trading-agent.

## Completed
- Read user master prompt and current official brief, contract, source policy, playbook, learning harness, challenge, guidelines and entry page.
- Downloaded and safely extracted official starter into vendor/signalpost-starter-kit, preserving original code and documentation.
- Requirement fetch timestamps and SHA-256: docs/requirements/provenance.json.
- Verified 411,160 eligible rows and both official universe hashes; selected disjoint seeded entry/development/validation/live-100 manifests.
- Starter saved refresh replay: 2 expected/observed changes, zero false changes, idempotent. Fixture evidence only.
- Audited the Codex-built implementation end-to-end (fetch broker, pipeline, extraction, refresh, runner, packaging, local UI) against the master prompt and official contract; confirmed no accidental duplication with the vendored starter.
- Found and fixed the largest coverage gap: `config/sources.json` had zero approved domains, so `Broker.permitted()` fail-closed every company-website fetch regardless of robots/identity-gate outcome, per the fetched source policy that lists company-owned sites as a preferred, non-third-party source category. Changed the policy from an allowlist to an explicit denylist/override (`aviscope/fetch.py`, `config/sources.json`, `SOURCE_RIGHTS.md`, `README.md`, `CRAWLERS.md`, `AGENT.md`); SSRF/DNS-pinning, robots.txt, budget caps, the restricted-platform hard-block and the exact-entity identity gate are unchanged. 149 tests / 5 subtests pass.
- Verified the fix live: a 10-company smoke run and a 100-company live holdout (`out/live-100-external/`) both dispatched real company-site fetches, correctly hit robots.txt/redirect blocks, and correctly quarantined ambiguous shared-portal/group/SPV candidates rather than publish them. Only 6/100 sampled companies had any registry-listed website at all; none of those 6 passed the identity gate in this sample. Generated the full 1,000-company entry corpus (`out/submission`) for a statistically larger read.
- Ran a real fixed-vs-gap routing comparison with external sources enabled (`reports/evaluation/routing-comparison.json`), replacing the previous hardcoded "external disabled" comparison logic in `scripts/evaluate_artifacts.py`.
- Checked `github.com/Avi36005/signalpost` (the master prompt's target repo): remote lookup returns not found; existence and permissions remain unverified. No repo was created or pushed to.

## Implementation plan
1. Typed claims and exact identity, a bounded DNS-pinned fetch broker, official extraction, source permissions, and immutable evidence.
2. Budgeted batch runner, gap-directed external routes, conflicts, refresh and checkpoint/resume.
3. Real local backend and accessible company/evidence/comparison/runs interface.
4. Meaningful regressions, live smoke and representative 100-company run, routing comparison, final 1,000-company corpus.
5. Freeze source, document actual results, audit a fresh extracted ZIP, and generate unsent email drafts.

## Current limits
No paid development budget supplied: all chargeable integrations disabled. Named third-party platforms (LinkedIn, Meta, Indeed, Glassdoor, Google/Bing, YouTube, X) remain hard-disabled pending licensed access; company-owned sites are enabled but full-corpus external hit rate is still being measured. No organizer gold/reference pool or independent human labels available. Do not report official qualification.

## External actions
Do not send emails, deploy, change visibility, grant access, or push until authorized. Continue all local work independently. Target repository `github.com/Avi36005/signalpost` could not be resolved (HTTP 404 is not proof of absence) — this is a genuine missing-permission blocker for the user to resolve (create/authorize the destination repo), not something resolved locally.

## Continuation checkpoint: 2026-09-14
- Re-read all nine official requirement pages and retained both old and current fetch provenance. Updated five-version allowance, sparse-pool gating and missed-batch ranking rules.
- Confirmed previous corpus was interrupted at 750/1,000 baseline profiles with no terminal files. It is preserved in out/submission; its elapsed deadline prevents a valid resumed research run.
- Existing 149 tests + five subtests passed. Added contact-page identity probing, distinct structured-evidence locators, HTML evidence auditing and prevention of conflicting website URLs. All 153 tests + five subtests pass.
- Packaging now uses the user-specified Signalpost destination instead of accidentally advertising the trading origin, and rejects mismatched/non-100 live reports.
- Next: freeze a local source commit, run fresh out/live-100-final and out/submission-final, audit actual results, validate UI journeys and generate the local incomplete-entry ZIP and unsent draft. Final measured continuation report will be reports/continuation-status.md and dist/latest.json; runtime artifacts are excluded from source freeze.
- No paid calls, remote push, deployment, invitation or email send authorized or performed. Repository access, manifest publication and contact remain pending.
