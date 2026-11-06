# November 2026 revision: feedback → behaviour → patch → validation → rollback

Source of the feedback: Soham's message of 2 November 2026 on Avinash's latest run, which was scored on the 108 companies it reached, not on all 300. This is feedback on one run, not a final score.

Branch: `feat/aviscope-soham-jbox-nov2026`. Agent changes: commit `0f142fb` (deadline, identity, revenue) and the social/packaging commit that follows this plan. The fresh measurements are in `EVAL.md` (November section).

## 1. Only 108 of 300 companies were reached

- **Feedback.** The run was scored on 108 of 300 companies.
- **What we know.** We do not have the organiser's command, commit, logs or output. So we cannot say why it happened. It might be missing outputs, unfinished work, rejected envelopes or an evaluator subset. We do not assume that 192 companies crashed, or that a particular network error was the cause.
- **What we found in the code.** Before `0f142fb`, `envelopes.jsonl` was written only after every future had finished. If a worker stalled, or an external timeout killed the process before then, the file held fewer envelopes than inputs, or none at all. That is one way to get fewer outputs than inputs. We have not shown it is what happened in the organiser's run.
- **Patch (`0f142fb`).**
  - The run has a monotonic deadline and keeps a flush margin.
  - Results are collected with `as_completed` timeouts, and the executor shuts down without blocking.
  - Every finished company is appended to `envelopes.partial.jsonl` as soon as it completes.
  - Companies that have not finished get an honest `failed` or partial profile.
  - The process exits on time even when a network thread is stuck.
  - An exhausted budget fails fast instead of sleeping through host throttle slots.
- **Validation.**
  - `tests/test_deadline.py` checks that 100, 300, 1,000 and 1,100 inputs give exactly one terminal envelope each, in input order, with a zero-request budget.
  - It also checks 300 and 1,100 inputs with sources that fail or are slow, stalled workers past the deadline, a process stuck in a network call, and that an exhausted budget does not book throttle slots.
  - We also ran the live 100-company test and a live 300-company holdout (`EVAL.md`).
- **Still open.** We have drafted an email (`docs/submission-drafts/clarification-108-of-300.txt`, unsent) asking for the original command, the commit, and what "108 reached" means.
- **Rollback.** Revert `0f142fb` (runner and fetch hunks). The October behaviour comes back, along with the risk of writing envelopes only at the end.

## 2. The summary mentions only 2025 revenue

- **Feedback.** The data holds 2023–2025 accounts, but the summary states only 2025.
- **Before.** The narrative named the latest filed revenue only.
- **Patch (`0f142fb`).** `revenue_comparison` and `revenue_sentence` in `aviscope/extract.py` compare the latest filed revenue with the year before, when both are comparable. Comparable means the same currency, unit and scope, with consecutive full-year periods. The sentence cites both revenue claims. If the inputs are zero, negative, missing, a different currency or scope, years with a gap, or a short period, it says so and does not compute a misleading percentage.
- **Validation.** `tests/test_revenue_summary.py`. The JBox site shows the same sentence, for example on `/company/924740760`: "Revenue was NOK 8.3 million in 2025, up from NOK 3.1 million in 2024 …".
- **Rollback.** Revert the `revenue_comparison` and `summarize` hunks. Narratives fall back to the latest year only.

## 3. The viewer only runs locally

- **Feedback.** Host the viewer and share a link.
- **Patch.**
  - `scripts/export_snapshot.py` builds a read-only public snapshot from terminal envelopes. It re-applies the current identity rule and drops snapshot paths, raw bodies, error traces and debug fields.
  - The published snapshot is `docs/site-snapshot/2026-10-smoke-100/`, at commit `0ca4301`.
  - We built a separate read-only site in JBox. Its public URL is https://build-the-actual-working-website-now-do.sites.jboxai.com/ and its provenance is in `docs/JBOX_BUILD_PROVENANCE.md`.
  - The site has no backend, no research execution, no keys and no arbitrary fetches. It is labelled "Research snapshot, retrieved 14 Oct 2026, not live data".
- **Validation.**
  - `tests/test_export_snapshot.py`.
  - Preview and public checks are recorded in the provenance file: search, profile, evidence receipt with focus and Escape, compare, methodology, 390 px with no overflow, and no console errors.
- **Rollback.** Unpublish the site in JBox. The local `aviscope.server` workbench is unchanged.

## 4. Two websites belonged to a group or parent

- **Feedback.** Publish a site only if the page shows the company's own name or number.
- **Before.** Tier 3 accepted a registry-declared homepage when its domain spelled the legal name, even if the page showed neither the name nor the number.
- **Patch (`0f142fb`).**
  - Every tier now needs the fetched page itself to show the exact legal name or the organisation number. A name-shaped host is only a ranking hint.
  - A same-host page that names a different legal entity, such as a sibling, parent or agency, does not inherit the host's ownership proof.
- **Validation.**
  - `tests/test_external_evidence.py`: a registry domain spelling the name without page proof is withheld; footer identity passes; parent, group and client-list homes are withheld; sibling pages are withheld.
  - `scripts/export_snapshot.py` re-applies the rule to older envelopes and reports what it withheld.
  - The three examples in the feedback (Grimstad Bil, Vorpå Lokalmat, Total Apartments) are not hardcoded.
- **Rollback.** Revert the `identity_gate` and `enrich` hunks of `0f142fb`.

## 5. Only websites came through: no social links, news or jobs

### Social links (added)

- **Before.** Profiles were taken from `<a href>` links and JSON-LD `sameAs` on verified pages. Handles had to spell the company name, brand or domain, and only one profile per platform was kept. Share, intent, login, dialog and personal links were already rejected.
- **Patch.** Facebook's current page form, `facebook.com/p/<Page-Name>-<numeric id>`, is now accepted. Before, every `/p/` path was rejected as a post. Instagram `/p/` posts, Facebook roots, login, share and dialog links, and an empty LinkedIn `/company/` are still rejected.
- **Label.** The identity basis says "Profile linked from the verified company website; destination not fetched" (or "declared in … structured data"). Platform pages are never fetched.
- **Validation.** `tests/test_aviscope.py::test_social_profile_links` (new cases), plus the existing tests for site-builder footers, personal pages and one profile per platform.
- **Rollback.** Revert the `fb_page` branch in `social_profile`.

### Independent news (blocked; documented)

- **Need.** An article from outside the company, found by search, that names the company exactly.
- **Policy.** `docs/requirements/sources.md` allows search APIs to find candidates, and licensed feeds. Search results are candidates, not evidence, so each article body would also need fetching and checking under its publisher's terms and robots rules.
- **What we checked (2026-11-06).**
  - GDELT DOC 2.0 is free and needs no key. Its terms page allows any use with a citation.
  - It returns only metadata (url, title, seendate, domain, language, sourcecountry), not article bodies.
  - In a polite probe of 12 smoke-sample companies, sent at least 6 s apart, 11 requests got HTTP 429. The response said "Please limit requests to one every 5 seconds". The one answered query returned 0 articles.
- **Why we did not add it.** At that reliability, a GDELT route would mostly produce `failed` states and add minutes to every batch. Publisher terms for fetching bodies would also need a review per domain. The licensed news feeds we know of are paid, and the brief rules out paid services without approval.
- **Current behaviour.** News is not established for most profiles. Company-site JSON-LD articles are still published from verified hosts. The fetch policy was not loosened.
- **To unblock.** Approve a licensed feed and its cost, or get an organiser-provided key. Then add it as a declared provider in `config/sources.json`, routed through the broker's budget and URL controls. Bodies should be retained as hash plus excerpt only.

### NAV jobs (blocked; documented)

- **What we checked (2026-11-06).**
  - NAV's `pam-stilling-feed` documentation says "Anyone can use this API free of charge", subject to its terms. Every request needs a bearer token.
  - The public token is for experiments and rotates at irregular intervals.
  - Production consumers must email NAV a written acceptance of the terms, with contact details, to be issued a token.
  - The feed is a full change stream with no query by employer. The employer `orgnr` appears only in each ad's detail record.
  - Inactive ads must be removed from consuming services.
- **Why we did not add it.**
  - Registering is an outward action on Avinash's behalf that hasn't been approved.
  - Using the experimental token in an official run would misuse it.
  - A correct integration means mirroring the whole feed, matching on exact `employer.orgnr`, and honouring ACTIVE/INACTIVE status and expiry.
- **Current behaviour.** Jobs come only from JSON-LD `JobPosting` on verified company pages, using exact employer and date validation (`job_dates_status`).
- **To unblock.** Avinash registers with NAV. Then add a declared provider that syncs the feed into a local index, matches exact `orgnr`, and publishes only ACTIVE ads that haven't expired, with their dates.

## 6. Updates may be 5–7 days apart

Refresh is unchanged. `--previous` compares material changes, and missing records are kept as stale rather than read as removals. The public site shows "No changes recorded: this snapshot is the first observation" and never makes up a timeline.

## Packaging

`scripts/package_submission.py` now:

- copies hand-written, unsent drafts from `docs/submission-drafts/`, where it used to generate outdated "not pushed" text with contact placeholders;
- records the public repository and the website URL;
- accepts `--extra-report` for the 300-company report;
- names the ZIP `AviScope_Avinash_Signalpost_<date>_<sha8>.zip`.

The source, report, code-hash and integrity checks are unchanged.
