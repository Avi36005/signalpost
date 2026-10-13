# Agent policy

`aviscope.runner` validates nine-digit Norwegian organisation numbers including their checksum. Each company receives official baseline processing before optional enrichment begins. The stable key is the legal organisation number, never a brand or name.

The baseline retrieves exact registry identity, latest available annual accounts, roles, subunits and group structure. A supplied frozen registry replaces live identity; an absent frozen row fails that company without publishing live replacements. `--history` additionally discovers available filing years. JSON pointers bind published values to retained evidence.

The website candidate comes from the official registry. Domain rights and robots are checked before access. The gate requires an official registry link, exact legal name and bounded exact organisation-number match, without competing organisation identifiers. Unverified/group/parked candidates remain quarantined. JSON-LD jobs and articles also require the target organisation identifier in the employer/subject.

The frozen routing choices are fixed observed-link order and gap-directed priority. Both operate on observed same-host links. Fixed remains the default CLI setting; `scripts/evaluate_artifacts.py --fixed --gap` compares measured runs once both are available, and `docs/AVISCOPE_DESIGN.md` / `reports/evaluation/routing-comparison.json` record whichever result is measured. No thresholds learn from hidden daily results.

Synthesis deterministically selects supported, undisputed legal-entity claims. It preserves dates, units, scope and unknowns; no LLM is enabled. A page's instructions are inert text, cannot invoke tools and cannot override identity gates. Missing jobs never imply no hiring. Promotional claims do not become independent sentiment.
