# Attribution and provenance

AviScope is developed for Avinash's Signalpost entry. It includes the official Signalpost starter distributed by Builderr, retained under `vendor/signalpost-starter-kit`.

Original archive SHA-256: `3a8bd83edd75fe788792ed7d060911236850d184605da3bdbefee44fcb6bb571`. The user-supplied archive and downloaded official archive are identical. URL and actual retrieval/verification timestamps: `docs/requirements/provenance.json` and `user-starter-provenance.json`.

Upstream modification: `src/norway_company_agent/operations.py` adds a psutil fallback for the Unix-only `resource` import on Windows. The original archive remains available from its official URL. No upstream licence file was supplied; no permissive licence is invented. Confirm release/distribution terms before publishing externally.

Original AviScope modules implement the shared network boundary, typed claim/evidence schema, strict identity gate, refresh, runner, audit/packaging and local workbench. Existing starter tests and notices are preserved. Third-party dependencies retain their own licences; their exact distributions are locked by `uv.lock`.
