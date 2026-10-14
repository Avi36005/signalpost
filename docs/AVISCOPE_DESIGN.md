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

Measured evidence (October 14, commit-pinned runs, see `EVAL.md`): on the identical September 100-company holdout and 1,000-company sample, the tiered gate, name-derived candidates, transport fixes and verified-site extraction raised website, brand, linked-profile and location coverage substantially. Integrity audits still pass. Every accepted external claim in the 100-company smoke test was reviewed by hand. These are traceability and coverage measures, not official accuracy.

October 14 transport fixes: HTTPS requests now send `Host` without `:443`; some servers answered the old header with an infinite self-redirect, which had masked valid company sites as "redirect limit reached". Connections try IPv4 first. A 4xx robots.txt means no restrictions (RFC 9309), and plain-HTTP sites get one HTTP attempt. Filing-copy reads have their own 2.1 s schedule, so `--history` no longer slows identity reads or starves website research.

Synthesis: `summarize` emits a narrative of short sentences. Each lists the claim ids it rests on (identity and industry, registered activity, the company's own description, latest legal-entity accounts, employees, leadership, head office and workplaces, verified web presence, jobs, latest article, changes, and the explicit unknowns). The envelope carries it as `summary`. The UI overview renders one source button per citation, and each opens the same receipt as the underlying fact.
