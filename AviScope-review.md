# AviScope review

Reviewed 14 October 2026. Repository: `/Users/avinashgehi3/projects/Avinash SignalPost`. This was a read-only review; existing changes and live runs were preserved.

## Measured baseline

The latest completed run inspected was `out/live-100-v4`, completed at 07:57:59 UTC, source-code hash `417b713dca842c0030109b6c144e8aaae9859d7badea0480fdbe562660f4a2cf`.

| Measure | Result |
|---|---:|
| Input companies / terminal outputs | 100 / 100 |
| Legal identity / financials | 100 / 100 |
| Leadership / locations | 99 / 99 |
| Verified website coverage | 7 |
| Company profile coverage | 4 |
| Jobs coverage | 0 |
| Public activity coverage | 1 |
| Requests / elapsed time | 835 / 257 seconds |
| Reported third-party cost | $0 |

These are coverage counts, not recall against a labeled ground truth. The report itself leaves official score and external precision unknown. All 100 profiles are partial.

The test suite passed: **186 tests plus 5 subtests**, with two dependency deprecation warnings. The v4 integrity audit also passed: 100 unique inputs and outputs, 489 retained snapshots hash-checked, 4,760 JSON locators and 26 HTML locators resolved, and 1,900 financial values matched to retained sources. This does not establish independent factual accuracy or eligible-universe membership; the latter was not checked in this audit invocation.

The preceding v3 run on the same input hash reported six websites, six company profiles and 70 locations. V4 reports seven, four and 99 respectively. This is a useful development comparison, but a live run is not a controlled test of any one change.

## Prioritized improvements

### 1. Fix false-positive legal-name matching before expanding discovery

**Confirmed by offline reproduction.** In `aviscope/extract.py`, around line 240, the website identity gate uses case-insensitive substring matching for the legal name. Combined with a matching domain, this accepts ordinary English “as” and even prefixes of longer words as the Norwegian legal suffix AS.

All three synthetic negative cases were accepted by the current gate without an organisation number:

| Target legal name | Candidate domain | Page text |
|---|---|---|
| GREYSTONE AS | greystone.com | Information provided to Greystone as a result of obtaining a financial product. |
| AMALIE AS | amalie.com | Follow AMALIE as we travel the world. |
| EXAMPLE AS | example.no | Welcome to Example Assistance. |

The gate described each as an exact legal-name match. These are demonstrations of a vulnerable matching rule, not claims about those real websites.

Use token boundaries and legal-name context. Boundaries alone fix “Assistance” but do not disambiguate English “as”. Require an independent identity signal where the suffix is ambiguous, such as an exact organisation number or corroborated registered address/contact. Matching a name-derived domain and the same ambiguous name text should not be treated as strong independent confirmation. Add these negatives and genuine Norwegian legal-name positives as regression tests.

### 2. Fall back when a registry-listed website fails

In `aviscope/pipeline.py:136`, guessed candidates are generated only when the candidate ledger contains no official-registry candidate. A dead, blocked or rejected registry URL therefore prevents this discovery path entirely.

Try the registry candidate first, then generate alternatives if verification fails and budget remains. Add former names, workplace names and suitably sourced email domains as candidate hints. Every alternative must pass the same identity checks; a hint is not proof. Record why each candidate was rejected so coverage losses are measurable.

### 3. Improve synthesis and deliver it to the evaluator

`aviscope/extract.py:421` selects only registered activity, industry, employees, revenue and annual result. It omits available leadership, company description, hiring and recent activity from its selected facts.

Build a short brief from supported claims covering business, identity, leadership, latest accounts, hiring/activity and explicit gaps. Preserve claim IDs and period/scope distinctions. This can be deterministic; adding a model is not necessary to fix coverage.

Separately, `aviscope/pipeline.py`'s `envelope()` omits `p['summary']`. An offline check confirmed that a populated profile summary is absent from the returned envelope. Consumers using only envelopes cannot see it. Check the evaluator contract and expose the synthesis in a supported output field or artifact, with an output-contract test.

### 4. Add jobs coverage with explicit date and employer checks

The latest run contains zero companies with jobs. Current extraction handles structured JobPosting data but does not check `validThrough` before adding a job claim (`aviscope/extract.py:385–392`). This is a code-path observation, not an observed expired job in this run.

Parse posting and expiry dates against a declared evaluation time; distinguish current from expired jobs, reject malformed/future dates appropriately, and preserve the dates as evidence. NAV is a candidate additional source: match exact organisation identifiers and verified workplace-to-parent relationships, and check active status/expiry. Measure its contribution on the actual company set rather than treating feed size as recall.

### 5. Recover homepage facts when identity is established on a contact page

When a contact page proves identity, the pipeline extracts facts there and uses the homepage chiefly for navigation. The existing test `test_contact_identity_is_scoped_to_verified_page` deliberately protects this behavior. It can also discard useful homepage descriptions.

A safe extension would cite two pieces of evidence: the contact page for entity identity and the homepage for the description. Require a consistent site identity, reject foreign identifiers and cross-domain assumptions, and preserve both source snapshots. Do not simply remove the existing safeguard.

## Evaluation plan

1. Freeze the current code hash, company inputs, evaluation time and request/time budgets.
2. Manually label a small representative set of website candidates, including failed registry URLs and ambiguous AS names.
3. Fix identity precision first and rerun those cases; accept that unsupported website counts may decrease.
4. Add fallback discovery and measure newly verified companies, false matches, requests and runtime separately.
5. Test synthesis citations and output delivery; add expired-job cases before increasing job coverage.
6. Rerun the same development and held-out company sets. Report coverage, independently checked precision and labeled recall separately.

The other Signalpost project's results use different inputs and cannot establish which implementation is better. No official score, qualification or leaderboard position can be inferred from these reports. Update stale documentation: some existing docs still describe 153 tests and older discovery behavior, while this review ran 186 tests.
