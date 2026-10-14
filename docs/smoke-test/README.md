# 100-company smoke-test result

The 100-company smoke test the October contract requires, run on commit `168f3ca` with:

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
| `scale-1000-*.json` | Optional 1,000-company local scale test on the same commit |

Result: 100/100 terminal envelopes, 0 failed inputs, 793 requests, 142 s, $0 third-party cost, integrity audit passed. Raw evidence snapshots (14 MB) are not committed; rerun the command to regenerate them. Measurements and the before/after comparison are in `EVAL.md`.
