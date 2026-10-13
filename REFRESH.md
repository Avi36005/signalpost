# Refresh and history

```sh
uv run python -m aviscope.runner --organisations data/smoke.jsonl --expected-count 10 --output-dir out/refresh --previous out/submission/profiles.jsonl --max-requests 200
```

Prior profiles are read by exact entity key and referenced evidence is copied into the new run with containment checks. Previous files are not edited. Stable keys use entity, field, reporting period, scope and an item key. Fetch timestamps and evidence versions do not turn unchanged values into business changes.

Supported new/changed claims expose before/after values, both evidence-ID sets, observation dates and a stable change ID. New filings, roles, locations and jobs have distinct types. No actual event date is invented from crawl time. Replaying the same snapshot creates no events. Missing records are retained as stale; a failed endpoint does not erase the prior supported value. A disappeared jobs page does not confirm job closure. Confirmed removals are not implemented; this limitation favors abstention.

An official HTTP 410 removal of the legal entity suppresses prior identity publication. It is a legal-removal signal, not an ordinary refresh failure. Old local artifacts require a review/removal procedure before redistribution; they are not silently treated as current evidence.

Run `scripts/evaluate_artifacts.py` on a live corpus to create a labelled unchanged-snapshot replay. The starter saved example and unit tests separately cover controlled changed/failed responses. Saved fixture checks are never labelled as live historical company changes.
