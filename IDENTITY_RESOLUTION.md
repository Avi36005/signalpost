# Exact entity publication

Official records are addressed by the input organisation number. Registry and annual-account response identifiers must equal that number. Subunit `overordnetEnhet` must equal it; the subunit's own number stays separate. Company roles are scoped to the public exact-entity role endpoint. Group responses remain group-scoped claims and never populate subsidiary financial metrics.

External website acceptance requires **all**: registry-listed candidate, exact full legal name on the page, exact bounded organisation-number match, no other nine-digit company identifier, and no parked-domain marker. Name similarity alone cannot authorize publication. This deliberately abstains on many valid but unproven websites; it is not measured 95% precision.

Adversarial tests cover name-only matches, franchise names, parent/shared identifiers, portfolio mentions, parked pages and numbers assembled from unrelated text. Compared with the starter's name-token threshold, these cases exercise stricter rejection, not independent quality measurement.

Identity links contain endpoints/domain, relationship type, status, source snapshot/locator or evidence IDs, and reasons. Rejected candidates stay in `candidate_ledger`. Roles and locations never get inferred from a brand's group site. Unresolved same-period/scope values enter `review_queue`; different periods and group/entity scopes are separate keys.

September 14 update: an inconclusive home page with no conflicting organisation identifiers may lead to at most two observed same-host contact links. Each page must independently pass the same exact-entity gate; contact-page proof never authorizes home-page claims. Subsequent pages no longer create conflicting official-website URLs. Structured claims have precise JSON-LD array/graph locators; the integrity auditor now checks HTML organisation spans, descriptions and structured values, including tampering regressions. Live improvement must be measured separately.
