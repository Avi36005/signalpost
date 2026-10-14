# AviScope

Avinash's Signalpost company research entry. A local research workbench for Norwegian legal entities: official identity, accounts, registered roles and workplaces, claim-level receipts, comparisons, refresh and measured batch runs.

**Current scope:** official Brønnøysund data (identity, filed accounts, roles, head office, registered workplaces, group links) for every company, plus exact-entity company-website research. AviScope reads the registry-declared homepage or, when none is declared, at most two DNS-resolving domains that spell the exact legal name. A tiered identity gate (`IDENTITY_RESOLUTION.md`) decides publication. From verified sites it publishes the website, description, brand name, linked company profiles, JSON-LD job postings and dated articles. Named third-party platforms (LinkedIn, Meta, Indeed, Glassdoor, Google/Bing, YouTube, X) are never fetched; only profile links found on a verified site are recorded. Each profile carries a deterministic, cited narrative summary. This is not an official qualification claim; see `LIMITATIONS.md`.

## Setup

Python 3.12.12 and uv are required. From this repository:

```sh
uv sync --frozen
uv run python scripts/prepare_data.py
```

The second command downloads and checks the eligible universe and reproduces seeded manifests. It is setup, not hidden company research. No credentials or paid APIs are required. Runtime/dependencies are pinned by `.python-version` and `uv.lock`. The starter and its lock remain under `vendor/signalpost-starter-kit`.

## Evaluator command

One pasteable command for any official batch file (JSONL `{"organisation_number": "..."}`, a JSON array, CSV with an organisation-number column, or one number per line). The batch size is not fixed: 100, 1,000 or 1,100 companies all work.

```sh
uv sync --frozen && uv run python -m aviscope.runner --organisations BATCH_FILE --output-dir out/official --history --max-cost 0
```

Defaults scale with the batch: 40 outbound requests per company and a wall-clock ceiling of max(2,600 s, 2.7 s per company). Set `--max-seconds` below the evaluator's time limit when Builderr publishes it. When the deadline arrives, remaining optional work stops and every company still receives its terminal envelope. `--expected-count N` optionally asserts the batch size.

For an evaluator-supplied frozen registry, append `--bulk frozen-brreg.csv --registry-retrieved-at ACTUAL_ISO_UTC_TIMESTAMP`. Raw Brreg entity JSONL/CSV and gzip variants are supported. Without `--bulk`, the command explicitly reports live development registry mode.

Optional flags: `--previous out/prior/profiles.jsonl` (refresh), `--cutoff ISO_UTC_TIMESTAMP`, `--resume`, `--routing fixed|gap`, `--workers 1..8` (registry), `--enrich-workers 1..64` (company websites, default 24), `--no-guess-domains`, `--source-policy config/sources.json`. See `DATA_SCHEMA.md` for the cutoff interpretation. Never use a historical cutoff with live reads and claim a historical reconstruction.

Each run writes `profiles.jsonl`, `envelopes.jsonl`, `entry-companies.jsonl`, `source-manifest.jsonl`, `evidence/`, `changes.jsonl`, `review-queue.jsonl`, `run-report.json` and `progress.json`. JSONL goes to files; stdout is a concise run report. A fresh output directory is required unless resuming exactly matching settings. Every validated unique input gets one terminal envelope even when research fails. A failed result is not a researched profile.

## Local workbench

```sh
uv run python -m aviscope.server --data-dir out/smoke-100 --port 8765
```

Open http://127.0.0.1:8765. Read a cited overview, research a number, search saved companies, compare two or three profiles, open any fact's evidence receipt, refresh a profile, or submit a batch under Runs & evidence. The UI uses actual backend outputs. It binds to loopback only. In an extracted submission package, run from `source/` with `--data-dir ../data`.

## 100-company smoke test and larger local tests

```sh
uv run python -m aviscope.runner --organisations data/live-100.jsonl --output-dir out/smoke-100 --history --max-cost 0
uv run python -m aviscope.audit --directory out/smoke-100 --universe downloads/universe.jsonl.gz --report reports/smoke-100-integrity.json
```

The October contract asks for this 100-company smoke-test result. Builderr supplies the companies for official scoring, so precomputed profiles are not submitted. The same command on `data/entry-companies.jsonl` is the optional 1,000-company scale test. No paid APIs are used.

## Verification and packaging

```sh
uv run python -m pytest -q
uv run python scripts/evaluate_artifacts.py --directory out/smoke-100 --output-dir reports/evaluation
uv run python scripts/package_submission.py --data-dir out/smoke-100 --live-report out/smoke-100/run-report.json
```

The packager requires a local Git commit and matching final live reports. It exports frozen source, builds the manifest and unsent email drafts, hashes payload files, extracts the ZIP and validates the extracted artifacts. See `SUBMISSION_README.md`.

Starter origin: https://builderr.ai/signalpost-starter-kit.tar.gz. See `NOTICE.md` for provenance and licensing limitations. Organizer-only npm checks listed in the contract are absent from the participant starter; this repository does not fake those checks.
