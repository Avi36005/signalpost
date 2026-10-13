# Data contract

Schema `aviscope-1` is defined by Pydantic in `aviscope/models.py` and exported to `schemas/profile.schema.json`. The public contract gives required sections and six states, not a downloadable normative JSON Schema. The adapter in `pipeline.envelope` implements those sections and the starter `OUTPUT_CONTRACT.md` envelope shape. Starter internal `complete/not_found/source_error` module states are not emitted as availability values.

A profile has organisation number/name, typed claims, evidence, source snapshots, per-family availability, identity links, candidate ledger, source decisions, conflicts, summary, refresh/changes, errors and operations. An envelope repeats claims/evidence/availability/snapshots/refresh/errors with exact organisation association and run terminal status (`completed` or `failed`). Missing/blocked modules coexist with a researched partial profile.

Availability: `available`, `not_available`, `blocked`, `not_applicable`, `ambiguous`, `failed`. Each family has a reason and attempted sources. A candidate's internal `not_attempted` status is operational metadata, not an evaluator availability state. Supported zero differs from null; a missing value never emits an available claim.

Claims carry a semantic key, value, field/family, availability, evidence IDs, period, currency, original unit, legal/group scope, first/last observation and stale status. Financial API values retain numeric currency units exactly; no multiplication based on guessed display units. Non-numeric API financial values are withheld. Norwegian text-number parsing is independently tested for optional extraction paths. No derived ratios are currently published.

Evidence carries entity ID, source URL/class, retrieval UTC time, original content hash, JSON pointer/HTML locator, extraction version and identity basis. Snapshots contain requested/final URLs, redirect chain, status/type, original hash, retained hash and package-relative file path. Role birth dates/identifiers are removed before storage; the retained hash records that transformation, and locators still resolve. A receipt hash is never presented as independently verified truth.

`--cutoff` currently means **latest permissible evidence retrieval time**, with the run's broker deadline reduced accordingly. It does not reconstruct historical knowledge from today's live source. Supply actual frozen-registry provenance; an older cutoff prevents live research. The organizer has not published a more precise cutoff schema: clarify the intended effective-time versus retrieval-time interpretation before daily execution.

Snapshot paths resolve relative to the run data directory. The package therefore stores evidence under `data/evidence/` to preserve these relationships without machine-specific paths. The packager validates every JSONL, snapshot hash, claim locator and financial source value.
