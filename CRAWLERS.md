# Sources and request policy

Enabled official endpoints on `data.brreg.no`: entity, annual accounts, company roles, subunits, group structure, and optional filing-year lookup. Versioned source policy: `config/sources.json`.

The evaluator uses `aviscope.fetch.Broker` for every outbound request. It validates URL and every redirect, verifies all DNS answers, connects to an already validated IP with TLS hostname verification, reserves a request before dispatch, and writes a reservation journal. Retry: at most one for transport failure, HTTP 429 or selected 5xx; no retry for 404/410. Redirect chain: at most five dispatches. Response cap: 2 MB. Timeout: at most 12 seconds per request, further bounded by remaining batch time. Aggregate byte cap: 8 GB. Concurrency: at most eight workers.

Official host starts are spaced by at least 0.18 seconds; filing-year starts by 2.1 seconds. Company-site starts are spaced by at least one second, additionally honoring robots crawl delay. Twelve consecutive transport/429/5xx failures open the host circuit breaker. Request counts include redirects/retries/robots. In-run exact-URL cache hits are separately counted; no undeclared persistent company response cache is loaded.

Static company HTML and JSON-LD extraction are enabled by default for a registry-linked company's own domain (per the official Signalpost source policy, which lists company-owned sources as preferred); `config/sources.json` `domains` is a per-domain denylist/override, not an allowlist gate. Named third-party platforms (LinkedIn, Meta, Instagram, Indeed, Glassdoor, Google, Bing, YouTube, X/Twitter) remain hard-disabled pending licensed access. The bounded queue follows observed links only. Browser rendering, search, PDFs, licensed social/jobs/news feeds, and model APIs are disabled. No unmetered browser traffic occurs in the evaluator.

Setup downloads (universe, requirements, dependencies) are separate, declared operations. No development-budget expenditure is hidden under the official $10 daily limit.
