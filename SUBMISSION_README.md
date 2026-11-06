# Reviewer entrypoint — AviScope

This is the **November 2026 revision bundle**, built around a fresh 100-company smoke test plus a 300-company local holdout run. It is not a qualified agent; only the organiser decides that. `docs/NOV2026_CHANGE_PLAN.md` maps the 2 November feedback to the changes. The generated `submission-manifest.json` is authoritative for source hash, actual counts, metrics and readiness blockers. All company data comes from live researched sources; tests/fixtures are explicitly separate. External coverage, independent quality review and starter source-release rights remain open. The repository is public.

## Package map

- `source/`: frozen Git-exported code, lockfiles, schemas, tests, documentation and notices.
- `data/`: exact selected manifest, profiles, terminal envelopes, source manifest, review queue and `evidence/`. Evidence is nested here so relative references work unchanged.
- `refresh/`: declared retained-live-corpus unchanged replay, changes and report. Controlled changed-source examples remain in source tests, not submission company data.
- `reports/`: the smoke-test run report, the 300-company holdout report (`nov2026-holdout-300-run-report.json`), the integrity audit and refresh results.
- `docs/`: final technical and rights documents plus browser screenshots.
- `email/`: the revision, website-only and 108-of-300 clarification emails, filled from the run reports.
- `SHA256SUMS.txt`: all payload files except itself. ZIP checksum is a separate sibling file outside the archive.

## Clean run

From `source/` run `uv sync --frozen`, then:

```sh
uv run python -m aviscope.runner --organisations reviewer-input.jsonl --output-dir out/reviewer --history --max-cost 0
uv run python -m aviscope.server --data-dir ../data --port 8765
```

The reviewer supplies `reviewer-input.jsonl` (JSONL, JSON array, CSV or one number per line; any batch size). It is not an undisclosed packaged hidden batch. Optional frozen registry: `--bulk reviewer-brreg.csv --registry-retrieved-at ACTUAL_UTC_TIME`. See `source/README.md` for exact modes and cutoff interpretation. No credential is required. Open http://127.0.0.1:8765 for the packaged real company profiles.

## Verification

`source/scripts/package_submission.py --verify PATH_TO_ZIP` rejects traversal, extracts to a fresh directory, checks payload checksums, parses JSON/JSONL and audits manifest/profile/envelope/evidence relationships. Initial packaging also performs a clean locked install and fresh offline zero-request cardinality smoke. That smoke proves package execution, not live coverage. Actual live results are separate reports.

Source: `https://github.com/Avi36005/signalpost` (public). Website: https://build-the-actual-working-website-now-do.sites.jboxai.com/ is a read-only JBox site over the October 100-company snapshot (`docs/JBOX_BUILD_PROVENANCE.md`). Retained company-site page bodies under `data/evidence/` are included so the evidence can be audited. They are not licensed for public redistribution.
