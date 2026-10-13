# AviScope design and evidence

The workbench answers: which legal entity is this, which claims have retained evidence, and what changed between observations?

```text
Organisation manifest / frozen registry
               |
      validated two-phase runner
               |
     DNS-pinned budgeted fetch broker
        /                  \
 official records      permitted company pages
        \                  /
    exact entity + deterministic extraction
               |
    claims + immutable evidence + conflicts
               |
       semantic refresh and synthesis
         /                      \
 JSONL evaluator + audit       local API / UI
```

Every company first receives baseline identity and official-data processing. An optional second phase examines its registry-linked website and filing history. No easy company can consume the entire external budget before others receive baseline opportunity.

The gap selector ranks observed same-domain links using internal missing-family priorities: jobs 5, activity 4, locations 3, leadership 2, brand 1. These are inspectable routing heuristics, not official scoring weights. The fixed comparator retains observed-link order. A selected route records family, reason, policy, request/byte/cost reservation, outcome and new supported claims. Registry-linked company websites are now researched by default (see `SOURCE_RIGHTS.md`); a measured fixed-vs-gap comparison on the identical `data/development.jsonl` cohort (`reports/evaluation/routing-comparison.json`) found no claim-count difference between the two orderings, so fixed remains the default until a cohort demonstrates an advantage. The routing regression separately verifies that an unresolved jobs page outranks a redundant about page, but that fixture is a unit test, not this live measurement.

Identity relations are typed list records with evidence and reasons. No graph database or decorative confidence score is used. A shared domain with multiple legal identifiers is ambiguous. Publication requires direct exact-entity evidence. Company-owned JSON-LD jobs/articles need entity-specific ownership in the structured record.

Receipts open from existing retained evidence without fresh source requests. They show value, entity, units, period, scope, retrieval time, locator, identity basis and both original/retained hashes. The raw HTML is never embedded. Financial equality is automatically verified against its JSON pointer; this does not replace independent accounting review.

Conflicts are grouped by semantic entity/field/period/scope/item key. Differing supported values are preserved, labelled ambiguous, queued for review and excluded from unqualified synthesis. Different annual periods or legal/group scopes are not averaged or silently merged. Official filed figures take precedence by restricting the financial extractor to filed-account APIs; external marketing cannot overwrite them.

Refresh distinguishes unchanged values, supported additions/changes, ambiguity and unsuccessful source reads. It retains old evidence and stale values. A new HTML template or disappeared page cannot assert a role ended. No precise real-world event date is invented.

Measured evidence: a 100-company live holdout run with company-owned sites enabled (`out/live-100-external/run-report.json`) produced 3,250 supported claims from 622 requests in 326 seconds, zero budget-check failures; of the sample, only 6 companies had any registry-listed website at all, and of those the identity gate published none — 2 were blocked by robots.txt/redirect limits and 4 were correctly quarantined as ambiguous (shared portals, group/SPV sites, insufficient exact-entity evidence). This shows the gate rejecting exactly the false-positive shapes it exists to catch rather than a defect; the entry-corpus run (`out/submission`) gives a larger-sample read on the true external-website hit rate. Starter saved refresh found two expected changes with zero false changes. These are traceability/regression measures, not official accuracy/coverage. Final live metrics and routing comparison live in the generated reports.

September 14 update: an inconclusive home page with no conflicting organisation identifiers may lead to at most two observed same-host contact links. Each page must independently pass the same exact-entity gate; contact-page proof never authorizes home-page claims. Subsequent pages no longer create conflicting official-website URLs. Structured claims have precise JSON-LD array/graph locators; the integrity auditor now checks HTML organisation spans, descriptions and structured values, including tampering regressions. Live improvement must be measured separately.
