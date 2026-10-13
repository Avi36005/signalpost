# Costs

Enabled APIs are unauthenticated official open-data endpoints; no chargeable third-party model/search API is called. The pipeline declares **$0 USD API spend** per run and for the corpus. The expected API spend per 100-company run is $0 while this configuration stays unchanged. This is not a claim that hosting, local electricity or labor is free.

Baseline measured smoke: 10 companies, 50 outbound requests, 14.063 seconds, $0 declared API cost. This pilot predates the final frozen release. Final measurements are in packaged `reports/submission-run-report.json` and `reports/live-100-report.json`; use those reports rather than extrapolating pilot timing.

Pricing basis dated 2026-09-13: public unauthenticated Brreg endpoints under the source documentation in `SOURCE_RIGHTS.md`, no paid provider configured. No model tokens are used. Development spend authorization is absent, so chargeable paths are disabled even though the competition allows up to $10 per 100-company daily run.

Requests include redirects/retries/robots. Package/dependency/requirements/universe downloads are setup and explicitly excluded from measured batch metrics; provenance records these downloads. No pre-crawled external website data is silently loaded. Any future hosted deployment or paid connector needs its own measured cost declaration.
