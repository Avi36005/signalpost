# 100-company smoke-test result

The 100-company smoke test the October contract requires, run on commit `62e36cc` (the submitted commit; the run report records the full hash in `source_commit`) with:

```sh
uv run python -m aviscope.runner --organisations data/live-100.jsonl --output-dir out/smoke-100 --history --max-cost 0
uv run python -m aviscope.audit --directory out/smoke-100 --universe downloads/universe.jsonl.gz --report reports/smoke-100-integrity.json
```

| File | Content |
|---|---|
| `smoke-100-input.jsonl` | The 100 organisation numbers (local holdout, not Builderr's batch) |
| `smoke-100-envelopes.jsonl.gz` | One terminal envelope per input: claims, evidence, availability, cited summary |
| `smoke-100-run-report.json` | Counts, requests, runtime, memory, field coverage, budget checks |
| `smoke-100-integrity.json` | Evidence audit: hashes, JSON pointers, financial equality, HTML locators |
| `scale-1000-*.json` | Optional 1,000-company local scale test, run earlier on commit `168f3ca` |

Result: 100/100 terminal envelopes, 0 failed inputs, 803 requests, 144 s, $0 third-party cost, integrity audit passed. Raw evidence snapshots (14 MB) are not committed; rerun the command to regenerate them. Measurements and the before/after comparison are in `EVAL.md`.

## November 2026 revision

The same 100 inputs were run again on commit `c39fb1e`, along with a new 300-company local holdout:

```sh
uv run python -m aviscope.runner --organisations docs/smoke-test/smoke-100-input.jsonl --output-dir out/nov2026-smoke --history --max-cost 0 --expected-count 100
uv run python -m aviscope.audit --directory out/nov2026-smoke --universe downloads/universe.jsonl.gz --report reports/nov2026-smoke-integrity.json
uv run python -m aviscope.runner --organisations docs/smoke-test/holdout-300-input.jsonl --output-dir out/nov2026-holdout-300 --history --max-cost 0 --expected-count 300
```

| File | Content |
|---|---|
| `nov2026-smoke-100-run-report.json` | 100/100 terminal, 0 failed, 799 requests, 144 s, $0 |
| `nov2026-smoke-100-integrity.json` | Evidence audit of that run: passed |
| `holdout-300-input.jsonl` | 300 organisation numbers (local holdout, not the organiser's 300) |
| `nov2026-holdout-300-run-report.json` | 300/300 terminal, 0 failed, 2,509 requests, 312 s, $0 |

Envelopes and evidence snapshots from these runs are not committed. Rerun the commands to regenerate them.
