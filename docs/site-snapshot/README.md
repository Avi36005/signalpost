# Public-site research snapshots

Read-only data for the hosted AviScope website. Each folder is one labelled export made by
`scripts/export_snapshot.py` from published terminal envelopes. It is not live data and does not cover all
Norwegian companies.

| Folder | Source run | Source commit | Companies | Retrieved |
|---|---|---|---|---|
| `2026-10-smoke-100/` | `aviscope-20261014T110930Z` (`docs/smoke-test/smoke-100-envelopes.jsonl.gz`) | `62e36ccf73b744d21f781d7fb6328071aa69304e` | 100 | 2026-10-14 |

Files: `manifest.json` (label, run, commit, checksums, exclusions), `index.json` (one search row per company),
`companies/<organisation_number>.json` (cited summary, claims, evidence receipts, availability, revenue comparison).

Excluded: local snapshot paths, retained page bodies, request journals, fetch logs, error traces, timings and
credentials. Evidence excerpts are capped at 240 characters. The export re-applies the November 2026 identity
rule: website, brand and profile claims backed only by a host-name match are withheld. None of the 7 confirmed
websites in this run needed withholding, because each one has on-page proof.

Regenerate with:

    uv run python scripts/export_snapshot.py --envelopes docs/smoke-test/smoke-100-envelopes.jsonl.gz \
      --report docs/smoke-test/smoke-100-run-report.json --out docs/site-snapshot/2026-10-smoke-100 \
      --label "AviScope research snapshot — 100 Norwegian companies, October 2026"
