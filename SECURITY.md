# Implemented execution controls

The supported runtime is a loopback-only local app and isolated CPU batch evaluator. This file documents implemented controls; it is not an independent security certification.

The shared fetch broker permits HTTP(S) only, no userinfo, embedded credential query keys, internal hostnames or nonstandard ports. Every DNS answer must be global unicast. IPv4, IPv6, mapped/transition addresses and redirect targets are checked. The selected public IP is pinned to the socket; TLS still verifies the original hostname. This avoids a second hostname resolution at connection time. No unrestricted proxy or browser fallback is enabled.

Budgets are reserved under a lock before dispatch. A journal records each request reservation, including redirects/retries. Per-host pacing, deadline/size caps and a circuit breaker limit work. JSON parsing is bounded by input/response size; files and previous snapshots require path containment. Unsafe archive paths, links and device members are rejected.

The API binds to 127.0.0.1, validates Host and rejects cross-origin writes. Research accepts bounded JSON organisation lists; it never runs submitted commands or arbitrary URLs. JSON-only POST avoids ordinary form CSRF. No CORS permission is granted. Only one workbench batch runs at a time. Deployment outside loopback requires an authenticated reverse proxy and separate review; the task did not authorize deployment.

The frontend escapes untrusted strings, rejects unsafe external-link schemes, adds noopener/noreferrer, and never renders scraped HTML. CSP disallows third-party scripts and frames. Source text never becomes tool instructions. No model or browser has access to repository secrets during extraction.

Birth dates/personal identifiers in public role payloads are removed before evidence storage. No private-role endpoints are called. Package creation exports the exact source commit and explicitly selected evidence, excluding .git, environments, keys, local logs, user files and unrelated archives. Heuristic secret scanning supplements the explicit file allowlist; it is not a mathematical proof of no secrets.
