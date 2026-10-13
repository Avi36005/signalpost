# AviScope

Avinash's Signalpost company research entry. A local research workbench for Norwegian legal entities: official identity, accounts, registered roles and workplaces, claim-level receipts, comparisons, refresh and measured batch runs.

**Current scope:** the free official-data pipeline is implemented. Registry-linked company-owned websites are researched by default (robots-checked, identity-gated); only named third-party platforms (LinkedIn, Meta, Indeed, Glassdoor, Google/Bing, YouTube, X) remain disabled pending licensed access. A company with no registry-listed website, or one that fails the exact-entity identity gate, still has an explicitly partial profile. This is not an official qualification claim; see `LIMITATIONS.md` and the generated package checklist.

## Setup

Python 3.12.12 and uv are required. From this repository:

```sh
uv sync --frozen
uv run python scripts/prepare_data.py
```

The second command downloads and checks the eligible universe and reproduces seeded manifests. It is setup, not hidden company research. No credentials or paid APIs are required. Runtime/dependencies are pinned by `.python-version` and `uv.lock`. The starter and its lock remain under `vendor/signalpost-starter-kit`.

## Evaluator command

For a reviewer-supplied 100-company JSONL file (`{"organisation_number":"945811714"}` on each line):

```sh
uv run python -m aviscope.runner --organisations evaluator-input.jsonl --expected-count 100 --output-dir out/evaluation --history --max-requests 2000 --max-seconds 2600 --max-cost 10
```

For an evaluator-supplied frozen registry, append `--bulk frozen-brreg.csv --registry-retrieved-at ACTUAL_ISO_UTC_TIMESTAMP`. Raw Brreg entity JSONL/CSV and gzip variants are supported. The eligible universe is a selection list, not a frozen identity snapshot. Without `--bulk`, the command explicitly reports live development registry mode.

Optional flags: `--previous out/prior/profiles.jsonl`, `--cutoff ISO_UTC_TIMESTAMP`, `--resume`, `--routing fixed|gap`, `--workers 1..8`, `--source-policy config/sources.json`. See `DATA_SCHEMA.md` for the cutoff interpretation. Never use a historical cutoff with live reads and claim a historical reconstruction.

Each run writes `profiles.jsonl`, `envelopes.jsonl`, `entry-companies.jsonl`, `source-manifest.jsonl`, `evidence/`, `changes.jsonl`, `review-queue.jsonl`, `run-report.json` and `progress.json`. JSONL goes to files; stdout is a concise run report. A fresh output directory is required unless resuming exactly matching settings. Every validated unique input gets one terminal envelope even when research fails. A failed result is not a researched profile.

## Local workbench

```sh
uv run python -m aviscope.server --data-dir out/submission-final --port 8765
```

Open http://127.0.0.1:8765. Research a number, search saved companies, compare two or three profiles, open any fact's evidence receipt, refresh a profile, or submit a batch under Runs & evidence. The UI uses actual backend outputs. It binds to loopback only. In an extracted submission package, run from `source/` with `--data-dir ../data`.

## Generate the entry corpus

```sh
uv run python -m aviscope.runner --organisations data/entry-companies.jsonl --expected-count 1000 --output-dir out/submission-final --max-requests 20000 --max-seconds 7200 --max-cost 0
uv run python -m aviscope.audit --directory out/submission-final --universe downloads/universe.jsonl.gz --report reports/submission-integrity.json
```

This larger **submission-corpus** budget is distinct from the daily 100-company evaluator ceiling. It uses no paid APIs. Available financial records are retained; add `--history` for rate-limited filing-year discovery. Historical PDF financial extraction is not enabled.

## Verification and packaging

```sh
uv run python -m pytest -q
uv run python scripts/evaluate_artifacts.py --directory out/submission-final --output-dir reports/evaluation
uv run python scripts/package_submission.py --data-dir out/submission-final --live-report out/live-100-final/run-report.json
```

The packager requires a local Git commit and matching final live reports. It exports frozen source, builds the manifest and unsent email drafts, hashes payload files, extracts the ZIP and validates the extracted artifacts. See `SUBMISSION_README.md`.

Starter origin: https://builderr.ai/signalpost-starter-kit.tar.gz. See `NOTICE.md` for provenance and licensing limitations. Organizer-only npm checks listed in the contract are absent from the participant starter; this repository does not fake those checks.
