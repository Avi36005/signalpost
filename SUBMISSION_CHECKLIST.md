# Submission checklist (November 2026 revision)

Builderr now asks for: the repository URL, the exact commit hash, a 100-company smoke-test result or report, one pasteable run command, the models/APIs/licences used, the expected cost per official run, an agent name and a contact. Precomputed profiles and a company manifest are no longer submitted. The current challenge page gives 16 November 2026 for entries and revisions (first version plus up to four revisions). The JBox website bonus closes on 7 November 2026, 23:59 IST.

- [x] Re-read the current challenge, brief, evaluation contract, playbook and source policy (2026-10-14; hashes in `docs/requirements/provenance.json`).
- [x] One command for any batch size and input format: `uv sync --frozen && uv run python -m aviscope.runner --organisations BATCH_FILE --output-dir out/official --history --max-cost 0`.
- [x] Clean-clone check: fresh clone, empty environment, `uv sync --frozen`, run command, full test suite.
- [x] Feedback mapped to changes, validation and rollback: `docs/NOV2026_CHANGE_PLAN.md`.
- [x] 100-company smoke test on the packaged commit: `out/nov2026-smoke/run-report.json` and `reports/nov2026-smoke-integrity.json`.
- [x] 300-company local holdout run (deadline-safe completion): `out/nov2026-holdout-300/run-report.json`.
- [x] JBox website published and checked: `docs/JBOX_BUILD_PROVENANCE.md`.
- [x] Optional 1,000-company local scale test (October, commit `168f3ca`; not rerun in November): `docs/smoke-test/scale-1000-run-report.json`.
- [x] Models/APIs/licences: no model; Brønnøysundregistrene open APIs (NLOD 2.0) and company-owned websites; $0 expected third-party cost per official run.
- [ ] Confirm starter redistribution terms (no LICENSE file in the starter archive).
- [x] Repository is public: `github.com/Avi36005/signalpost`.
- [ ] Organiser's command, commit and logs for the 108-of-300 run (clarification drafted).
- [ ] NAV job-feed registration and a licensed news provider (both blocked; see `LIMITATIONS.md`).
- [ ] Ask Builderr for the official run's time limit and set `--max-seconds` below it.
- [ ] Avinash confirms the results contact and approves sending the email to `submit@builderr.ai`.

Qualification stays `not_determined` until Builderr scores an official run.
