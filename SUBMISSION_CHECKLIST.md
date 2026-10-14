# Submission checklist (October 2026 contract)

Builderr now asks for: the repository URL, the exact commit hash, a 100-company smoke-test result or report, one pasteable run command, the models/APIs/licences used, the expected cost per official run, an agent name and a contact. Precomputed profiles and a company manifest are no longer submitted. Revisions are accepted until Oct 18 (five versions in total).

- [x] Re-read the current challenge, brief, evaluation contract, playbook and source policy (2026-10-14; hashes in `docs/requirements/provenance.json`).
- [x] One command for any batch size and input format: `uv sync --frozen && uv run python -m aviscope.runner --organisations BATCH_FILE --output-dir out/official --history --max-cost 0`.
- [x] Clean-clone check: fresh clone, empty environment, `uv sync --frozen`, run command, full test suite.
- [x] 100-company smoke test on the pushed commit: `out/smoke-100/run-report.json` and `reports/smoke-100-integrity.json` (100/100 terminal envelopes, audit passed).
- [x] Optional 1,000-company local scale test: `out/scale-1000/run-report.json`.
- [x] Models/APIs/licences: no model; Brønnøysundregistrene open APIs (NLOD 2.0) and company-owned websites; $0 expected third-party cost per official run.
- [ ] Confirm starter redistribution terms (no LICENSE file in the starter archive).
- [ ] Give Builderr reviewers read access to `github.com/Avi36005/signalpost` at the submitted commit.
- [ ] Ask Builderr for the official run's time limit and set `--max-seconds` below it.
- [ ] Send the submission email to `submit@builderr.ai` (never sent automatically).

Qualification stays `not_determined` until Builderr scores an official run.
