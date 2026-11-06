# AviScope

Avinash's Signalpost company research entry: a research agent for Norwegian legal entities, covering official identity, accounts, registered roles and workplaces, claim-level receipts, comparisons, refresh and measured batch runs.

**Website:** https://build-the-actual-working-website-now-do.sites.jboxai.com/ is a read-only site built with JBox over a labelled 100-company research snapshot (retrieved 14 October 2026; `docs/site-snapshot/`, `docs/JBOX_BUILD_PROVENANCE.md`). It is not live data. **November 2026 revision:** `docs/NOV2026_CHANGE_PLAN.md` maps each item of the organiser's feedback to its change, validation and rollback.

**Current scope:** official Brønnøysund data (identity, filed accounts, roles, head office, registered workplaces, group links) for every company, plus exact-entity company-website research. AviScope reads the registry-declared homepage or, when none is declared, at most two DNS-resolving domains that spell the exact legal name. A tiered identity gate (`IDENTITY_RESOLUTION.md`) decides publication, and every tier needs the page itself to show the exact legal name or organisation number. From verified sites it publishes the website, description, brand name, linked company profiles, JSON-LD job postings and dated articles. Named third-party platforms (LinkedIn, Meta, Indeed, Glassdoor, Google/Bing, YouTube, X) are never fetched; only profile links found on a verified site are recorded. Each profile carries a deterministic, cited narrative summary, including the latest filed revenue against the preceding comparable year. Searched news and NAV job ads are not enabled (see `LIMITATIONS.md`). This is not an official qualification claim; see `LIMITATIONS.md`.

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

Defaults scale with the batch: 40 outbound requests per company and a wall-clock ceiling of max(2,600 s, 2.7 s per company). Set `--max-seconds` below the evaluator's time limit when Builderr publishes it. The run keeps a margin before its deadline to write output. Each finished company is appended to `envelopes.partial.jsonl` straight away. When the deadline arrives, remaining work stops and every company still receives exactly one terminal envelope (failed or partial if needed). `--expected-count N` optionally asserts the batch size.

For an evaluator-supplied frozen registry, append `--bulk frozen-brreg.csv --registry-retrieved-at ACTUAL_ISO_UTC_TIMESTAMP`. Raw Brreg entity JSONL/CSV and gzip variants are supported. Without `--bulk`, the command explicitly reports live development registry mode.

Optional flags: `--previous out/prior/profiles.jsonl` (refresh), `--cutoff ISO_UTC_TIMESTAMP`, `--resume`, `--routing fixed|gap`, `--workers 1..8` (registry), `--enrich-workers 1..64` (company websites, default 24), `--no-guess-domains`, `--source-policy config/sources.json`. See `DATA_SCHEMA.md` for the cutoff interpretation. Never use a historical cutoff with live reads and claim a historical reconstruction.

Each run writes `profiles.jsonl`, `envelopes.jsonl`, `entry-companies.jsonl`, `source-manifest.jsonl`, `evidence/`, `changes.jsonl`, `review-queue.jsonl`, `run-report.json` and `progress.json`. JSONL goes to files; stdout is a concise run report. A fresh output directory is required unless resuming exactly matching settings. Every validated unique input gets one terminal envelope even when research fails. A failed result is not a researched profile.

## Local workbench (development)

```sh
uv run python -m aviscope.server --data-dir out/nov2026-smoke --port 8765
```

Open http://127.0.0.1:8765. Read a cited overview, research a number, search saved companies, compare two or three profiles, open any fact's evidence receipt, refresh a profile, or submit a batch under Runs & evidence. The UI uses actual backend outputs. It binds to loopback only. In an extracted submission package, run from `source/` with `--data-dir ../data`.

## 100-company smoke test and larger local tests

```sh
uv run python -m aviscope.runner --organisations docs/smoke-test/smoke-100-input.jsonl --output-dir out/nov2026-smoke --history --max-cost 0 --expected-count 100
uv run python -m aviscope.audit --directory out/nov2026-smoke --universe downloads/universe.jsonl.gz --report reports/nov2026-smoke-integrity.json
uv run python -m aviscope.runner --organisations docs/smoke-test/holdout-300-input.jsonl --output-dir out/nov2026-holdout-300 --history --max-cost 0 --expected-count 300
```

`docs/smoke-test/smoke-100-input.jsonl` is the same seeded 100-company list as `data/live-100.jsonl`, written by `scripts/prepare_data.py`. `holdout-300-input.jsonl` is a disjoint seeded local sample, not the organiser's 300. The contract asks for the 100-company smoke-test result. Builderr supplies the companies for official scoring, so precomputed profiles are not submitted. The same command on `data/entry-companies.jsonl` is the optional 1,000-company scale test. No paid APIs are used.

## Verification and packaging

```sh
uv run python -m pytest -q
uv run python scripts/evaluate_artifacts.py --directory out/nov2026-smoke --output-dir reports/evaluation
uv run python scripts/package_submission.py --data-dir out/nov2026-smoke --live-report out/nov2026-smoke/run-report.json --extra-report out/nov2026-holdout-300/run-report.json
uv run python scripts/package_submission.py --verify dist/AviScope_Avinash_Signalpost_DATE_SHA.zip
```

The packager requires a clean tracked tree whose commit and code hash match the run reports. It exports frozen source, builds the manifest, copies the unsent drafts from `docs/submission-drafts/` (filling `{{fields}}` only from the run reports), hashes payload files, extracts the ZIP and validates the extracted artifacts with a clean offline install. See `SUBMISSION_README.md`.

Starter origin: https://builderr.ai/signalpost-starter-kit.tar.gz. See `NOTICE.md` for provenance and licensing limitations. Organizer-only npm checks listed in the contract are absent from the participant starter; this repository does not fake those checks.
