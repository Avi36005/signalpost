# JBox build brief: AviScope website

Paste **only the text block below** into the JBox composer for the account avinashgehi3@gmail.com. Don't paste this
heading or the notes after the block.

The dataset URLs are pinned to commit `0ca4301b45b03f10d4d30d965808fe9f7ebc7c27` of
https://github.com/Avi36005/signalpost. They only resolve after that commit has been pushed to the public repository.

```text
Build the actual working website now. Do not write another prompt document or a markdown specification as the final deliverable.

Project name: AviScope. This is Avinash Gehi's Signalpost company-research entry, backed by https://github.com/Avi36005/signalpost. Preserve that existing Python agent. Build a separate, read-only frontend that loads a published research snapshot. No backend, database, Supabase, authentication or paid service is needed.

Tagline: "See the company. Verify the story."
Supporting text: "Explore Norwegian businesses, compare filed accounts, and inspect the evidence behind each fact."
Context line: "Norwegian company intelligence · Signalpost entry"

Visual direction: midnight navy hero (#0A1725), warm paper research screens (#F6F5EF), ink text (#142638), strong teal controls (#006F67), restrained amber for uncertain or not-established states. Clean sans typography, tabular figures, short monospace organisation-number labels, thin dividers, restrained rounded surfaces. Check real contrast.

Create an original interactive 3D research lens/compass over abstract fjord contours. A central company identity card sits behind the lens; restrained Accounts, Website, People, Jobs and News tiles orbit it, joined by fine evidence lines. It is an illustration, not a data graph. Gentle damped pointer tilt and bounded drag rotation, keyboard rotate/reset and Pause controls, prefers-reduced-motion support, pause when offscreen or tab hidden, capped pixel ratio, lazy-loaded 3D, WebGL-failure handling and a static SVG fallback. Desktop: editorial headline and search on the left, scene on the right. Mobile: search first, compact scene below; never trap touch scrolling. Search and navigation work immediately, before and without 3D.

Give it a distinctive, premium finish: an editorial hero with intentional line breaks, an asymmetric desktop layout and a separately composed mobile layout; refined revenue-history charts with an equivalent accessible table; source chips beside facts; a readable evidence-receipt drawer; a polished comparison tray. Consistent spacing, borders, icons and all interaction states (hover, focus, pressed, loading, disabled, error). Avoid generic card grids, stock AI/robot imagery, emoji icons, heavy glass blur, gradient blobs, decorative fake charts, lorem ipsum and invented statistics.

Navigation: AviScope wordmark, Explore, Compare, Methodology, Search.

Build these working pages and flows:
1. Landing: tagline, company-name/organisation-number search, Explore and Compare actions, the 3D lens, the real dataset label and retrieval date from the manifest, and these genuine example companies from the snapshot: EN FORSKJELL AS (924740760), OSLO LUNSJ AS (912112276), INTERIØRSENTERET TRØNDELAG AS (981112121), REVISORTEAM AS (936766749).
2. Explorer: search by name or 9-digit organisation number with Norwegian characters (æ, ø, å) and case-insensitive matching; filters for municipality, legal form, industry (description), "has confirmed website" and "has revenue"; sort by name or latest revenue; pagination; columns name, org. no., place, industry, latest revenue with year, last checked. Keep query/filter/page in the URL. Show the dataset size ("100 companies in this snapshot"). States: loading, no match, invalid organisation number (not 9 digits), empty dataset, fetch error.
3. Company profile (/company/{organisation_number}): legal identity, the cited overview from summary.narrative, the latest-versus-prior revenue sentence from summary.revenue_comparison_text, a revenue-history chart plus table from revenue_history (missing years stay visibly missing; show currency), other filed figures (annual_result, operating_result, equity, assets, debt) by period, leadership (registered_role), head office and workplaces, confirmed website and linked social profiles, jobs, news/public activity, and an explicit "Not established" list from summary.unknowns and availability. Every fact has a source chip that opens its evidence.
4. Comparison (/compare?ids=a,b): pick two companies (optional third if it stays clear). Align fields; show each side's reporting year, currency and scope; flag different reporting years; evidence access per side. On phones use paired rows or tabs, not a squeezed wide table. No "winner" rankings. Desktop sticky tray and mobile bottom action for selection, persisted in the URL.
5. Evidence receipt: desktop drawer, mobile bottom sheet. Show the fact, source domain and link, source class, retrieved time, reporting period or effective date, short supporting excerpt when present, identity basis. Keep evidence id, locator and content_sha256 inside an expandable "Technical details". Focus trap, Escape to close, focus return, labelled controls. Only open http/https links, with rel="noopener noreferrer". A hash is not proof a claim is true; don't describe it that way.
6. Changes and methodology: a Changes section on each profile from the changes array (it is empty for every company in this first snapshot, so show "No changes recorded: this snapshot is the first observation" and never a fictional timeline). A Methodology page explaining: official Brønnøysund registry and filed-accounts sources, exact-company identity proof (a website is shown only when the page itself names the exact legal name or organisation number), "not established is not proof of absence", the snapshot label/date/run id/source commit from the manifest, and its limits (a 100-company sample, not live, not all of Norway).

DATA: load this real, versioned AviScope research snapshot at runtime with fetch (no build-time bundling of all files, no invented records):
Base URL: https://cdn.jsdelivr.net/gh/Avi36005/signalpost@0ca4301b45b03f10d4d30d965808fe9f7ebc7c27/docs/site-snapshot/2026-10-smoke-100/
- manifest.json: label, mode ("research_snapshot"), description, company_count (100), run_id ("aviscope-20261014T110930Z"), source_commit, source_repository, retrieved_from, retrieved_to, exported_at, identity_rule, excluded.
- index.json (about 42 KB): array of rows {organisation_number, legal_name, legal_form, municipality, postal_place, industry:{kode, beskrivelse}|null, employees|null, latest_revenue:{value, currency, year}|null, revenue_change_percent|null, website|null, families_available, claim_count, checked_at}. Use it for search, filters and examples.
- companies/{organisation_number}.json (load on demand when a profile or comparison opens): {schema_version, organisation_number, legal_name, run, summary:{title, narrative:[{text, claim_ids}], unknowns:[family], revenue_comparison|null, revenue_comparison_text|null}, revenue_history:[{year, period:{fraDato, tilDato}, value, currency, original_unit, claim_id}], claims:[{id, field, family, value, availability, evidence_ids, period, effective_at, currency, original_unit, scope, derived_from, stale, first_observed_at, last_observed_at}], evidence:[{id, source_url, source_class, retrieved_at, locator, identity_basis, retention, content_sha256, extraction_method, excerpt|null}], availability:{family:{state, reason}}, changes:[], refresh, withheld_by_current_identity_rule:[]}.
Families: legal_identity, brand, financials, financial_history, leadership, locations, group, website, company_profiles, jobs, public_activity. Availability states include available, not_available, ambiguous, blocked, failed; show reason text for anything not available. Claim values can be strings, numbers or objects (addresses have adresse, postnummer, poststed, kommune; registered_role values hold the role and person/organisation). Money values are in whole currency units (NOK); format them as NOK with thousands separators or "NOK 8.3 million", never as zero when missing. Keep currency, scope and period beside every figure. Use only available, non-stale claims as current facts; label stale ones "historic". Narrative sentences cite claim_ids; map them to evidence_ids for source chips.
Put the data loading in one small adapter module with a single DATA_BASE_URL constant, typed parsing, and the loading/empty/error states above. If the URL fails, show an honest "Snapshot unavailable" state with a retry, never fake data. Show the manifest label and the retrieval date on the landing page and in the footer ("Research snapshot, retrieved 14 Oct 2026, not live data").

Keep public browsing read-only. Do not expose research-job execution, API keys, arbitrary URL fetches, local filesystem paths or raw logs. Do not enable Supabase or a paid service.

Make the main tasks easy on laptop and phone (360/390 px, 768 px, 1440 px): find a company, compare two, inspect a source. Semantic HTML, keyboard navigation, visible focus, contrast-compliant colours, touch-friendly controls, no horizontal page overflow, no hover-only actions. Do not invent testimonials, users, accuracy percentages, awards, coverage claims or change history.

If you are in Plan mode, propose a plan for the actual website screens, data adapter and implementation, then proceed through your supported build workflow when that plan is accepted. Do not propose creating a prompt or specification file as the project result. Return a real interactive preview, then the public URL after publication. Clearly identify any remaining data or deployment blocker.
```

## Notes, not for JBox

- If JBox proposes only a document, reply: "The deliverable is the working AviScope web application. Do not
  create another prompt file. Keep the requested screens and design, implement them, and show the interactive
  preview. Use honest empty states until the dataset is supplied."
- In this snapshot, 7 companies have a confirmed website. All have on-page proof, so the current identity rule withheld none.
  4 have linked company profiles (social). 87 of the 100 have a filed revenue figure. Jobs were not established
  for any company; public activity was established for 1. The site must say "not established" rather than hide those sections.
  Website states: 7 available, 20 ambiguous, 8 blocked, 65 not available.
- Use bounded refinement requests after the first build. Do not regenerate the whole site.
