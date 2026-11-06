# JBox build provenance: AviScope website

This records how the hosted AviScope website was produced in JBox. It contains no secrets.

## Account

- JBox account: avinashgehi3@gmail.com. Checked in the JBox account menu on 2026-11-06 before the project was created.
  The menu showed "Credits: 20 available".
- No other person's JBox project was opened, reused or modified.

## Project

- JBox project: https://jboxai.com/project/y06trcf4z83deprokeqgxs08/
- Created: 2026-11-06 (prompt submitted 16:15 IST), model setting "Atlas, Standard", Plan mode.
- Prompt: the text block in `docs/JBOX_AVISCOPE_BUILD_PROMPT.md` (commit `d32199c`), pasted as is.
- JBox's plan (summarised): an editorial navy landing page with search and an original 3D research lens plus a static
  fallback; a paper-toned Explorer; company profiles with revenue charts and tables; a two-company comparison saved in
  the URL; evidence receipts; honest availability and change states; a methodology page. The plan says there is no
  backend, login or paid service, and the Python agent is untouched. The plan was accepted because it builds the
  working application, not a document.

## Data

- Source: real AviScope output from run `aviscope-20261014T110930Z` (100 Norwegian companies, retrieved
  2026-10-14), produced by agent commit `62e36ccf73b744d21f781d7fb6328071aa69304e`.
- Export: `scripts/export_snapshot.py` → `docs/site-snapshot/2026-10-smoke-100/` in commit
  `0ca4301b45b03f10d4d30d965808fe9f7ebc7c27`.
- The site loads it at runtime, read-only, from
  `https://cdn.jsdelivr.net/gh/Avi36005/signalpost@0ca4301b45b03f10d4d30d965808fe9f7ebc7c27/docs/site-snapshot/2026-10-smoke-100/`
  (checked 2026-11-06: manifest, index and company files return HTTP 200 with `access-control-allow-origin: *`).
- No Supabase, database, environment secrets or paid services were enabled.

## Build, preview and publication

- First build: completed 2026-11-06, 16:23 IST. JBox added a 10-credit first-build reward, so the balance was 35.
- Preview: https://y06trcf4z83deprokeqgxs08.preview.jboxai.com/
- Preview checks (2026-11-06, Chrome):
  - Landing: the tagline, search, 3D lens (labelled "Illustration, not a data graph") and Pause/Reset controls, the
    manifest label and retrieval date, and the four example companies all rendered.
  - Explorer: `?q=trøndelag` returned INTERIØRSENTERET TRØNDELAG AS; `?q=12345` showed "Enter a 9-digit
    organisation number". Filters and "100 companies in this snapshot" were shown.
  - Profile `/company/924740760`: cited overview; the revenue sentence "Revenue was NOK 8.3 million in 2025, up from NOK
    3.1 million in 2024, an increase of NOK 5.2 million (164.0%)"; other filed figures by period; leadership;
    locations; the confirmed website and Facebook profile; jobs, news and group shown as "Not established" with reasons;
    "No changes recorded: this snapshot is the first observation".
  - Evidence receipt: opens as a modal dialog with the source, retrieval time, identity basis and collapsed technical
    details, and closes on Escape.
  - Compare `?ids=924740760,912112276`: aligned fields with period, currency and scope beside each value; no ranking.
  - Methodology: sources, the exact-identity rule, "not established is not proof of absence", limits, and the
    manifest's run id and source commit.
  - Width: at 390 px there was no horizontal page overflow on any of the five pages. Only the decorative SVG contours
    extend past the edge, and they are clipped. No console errors.
- Refinement (one bounded request, 16:29–16:32 IST, 6 credits), with the following fixes:
  - The revenue-history chart and table were missing because `revenue_history[].year` is a string in the snapshot.
    The site now parses both forms. On `/company/924740760` it shows 2023, 2024 and 2025 (NOK 1,492,036,
    3,145,634 and 8,305,785), each with a source chip.
  - Compare showed only one registered role per company. It now lists all of them.
- Published: 2026-11-06, about 16:35 IST, with JBox's Publish control after the signed-in account
  (avinashgehi3@gmail.com) was checked again in the account menu. Publishing used 1 credit, leaving 28.
- Public URL: https://build-the-actual-working-website-now-do.sites.jboxai.com/
  Checked after publication: the landing page and `/company/924740760` load the real snapshot, including the revenue
  sentence and history table, and the footer says "Research snapshot, retrieved 14 Oct 2026, not live data". The page
  contacts only its own host and `cdn.jsdelivr.net`.
- Hosting cost: JBox's publish panel estimates 1 credit per day (7 credits for 7 days, about 30 for 30 days). Nothing
  was bought, and no billing settings were changed.
- Generated source: it stays in the JBox project above. It was not exported into this repository, so this repository
  holds no JBox-generated frontend code.
