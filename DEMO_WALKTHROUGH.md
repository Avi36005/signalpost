# Real local demo

1. Start `uv run python -m aviscope.server --data-dir out/submission`. Open http://127.0.0.1:8765. Search an included company or research organisation `945811714` (AMBITA AS) through the real official API.
2. Click a revenue value. Check its legal entity, NOK currency, reporting period, numeric JSON pointer, retrieval time and original/retained hashes. Closing/reopening the receipt makes no new company-source request.
3. Select two or three companies in the explorer and choose Compare. Unknown values stay unknown and each financial amount retains its reporting period/currency.
4. Open a company and select Refresh evidence. Watch Runs & evidence. A real unchanged source correctly creates no material changes; source failures retain supported prior values as stale.
5. Inspect research gaps and source/identity details. No external source or independent accuracy badge is invented.

Desktop explorer, evidence panel and 390×844 mobile-profile screenshots are included in the final package under `docs/screenshots/`. They show real smoke profiles, not fixture rows. API and keyboard dialog behavior are covered by the local validation report.
