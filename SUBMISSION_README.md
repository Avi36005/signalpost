# Reviewer entrypoint — AviScope

This is a **local, incomplete-entry review bundle**, not a submitted or qualified agent. The generated `submission-manifest.json` is authoritative for source hash, actual counts, metrics and readiness blockers. All company data is live researched official data; tests/fixtures are explicitly separate. External coverage, independent human quality review, source-release rights and reviewer access remain pending.

## Package map

- `source/`: frozen Git-exported code, lockfiles, schemas, tests, documentation and notices.
- `data/`: exact selected manifest, profiles, terminal envelopes, source manifest, review queue and `evidence/`. Evidence is nested here so relative references work unchanged.
- `refresh/`: declared retained-live-corpus unchanged replay, changes and report. Controlled changed-source examples remain in source tests, not submission company data.
- `reports/`: corpus run, live-100 run, integrity/quality notes and test results.
- `docs/`: final technical and rights documents plus browser screenshots.
- `email/`: unsent TXT/EML submission and clarification drafts.
- `SHA256SUMS.txt`: all payload files except itself. ZIP checksum is a separate sibling file outside the archive.

## Clean run

From `source/` run `uv sync --frozen`, then:

```sh
uv run python -m aviscope.runner --organisations reviewer-input.jsonl --expected-count 100 --output-dir out/reviewer --history --max-requests 2000 --max-seconds 2600 --max-cost 10
uv run python -m aviscope.server --data-dir ../data --port 8765
```

The reviewer supplies `reviewer-input.jsonl`; it is not an undisclosed packaged hidden batch. Optional frozen registry: `--bulk reviewer-brreg.csv --registry-retrieved-at ACTUAL_UTC_TIME`. See `source/README.md` for exact modes and cutoff interpretation. No credential is required. Open http://127.0.0.1:8765 for the packaged real company profiles.

## Verification

`source/scripts/package_submission.py --verify PATH_TO_ZIP` rejects traversal, extracts to a fresh directory, checks payload checksums, parses JSON/JSONL and audits manifest/profile/envelope/evidence relationships. Initial packaging also performs a clean locked install and fresh offline zero-request cardinality smoke. That smoke proves package execution, not live coverage. Actual live results are separate reports.

No email was sent, repository visibility changed, reviewer invited, or hosted deployment published. The repository URL in the manifest reflects the configured origin; exact remote source availability is still pending until an authorized push/access check.
