from __future__ import annotations

from copy import deepcopy

from .models import digest, now


def apply_refresh(current: dict, previous: dict | None):
    if not previous:
        current['refresh'] = {'previous_available': False, 'checked_at': now(), 'material_changes': 0, 'reason': 'Initial observation; no invented history'}
        return current
    if current['organisation_number'] != previous['organisation_number']:
        raise ValueError('Previous snapshot belongs to another company')
    old = {c['semantic_key']: c for c in previous['claims']}
    current['changes'] = []
    for claim in current['claims']:
        prior = old.get(claim['semantic_key'])
        if prior:
            claim['first_observed_at'] = prior['first_observed_at']
        if prior and digest(prior['value']) == digest(claim['value']):
            continue
        if claim['availability'] != 'available':
            continue
        kind = 'changed_value' if prior else {'financials': 'new_filing', 'leadership': 'new_role', 'locations': 'new_location', 'jobs': 'new_job'}.get(claim['family'], 'new_supported_claim')
        current['changes'].append({'id': 'ch-' + digest([claim['semantic_key'], prior['value'] if prior else None, claim['value']])[:24], 'organisation_number': current['organisation_number'], 'field': claim['field'], 'type': kind, 'material': True, 'previous_value': prior['value'] if prior else None, 'current_value': claim['value'], 'previous_evidence_ids': prior['evidence_ids'] if prior else [], 'current_evidence_ids': claim['evidence_ids'], 'first_observed_at': claim['first_observed_at'], 'observed_at': claim['last_observed_at'], 'event_date': None, 'date_basis': 'Observation time; exact real-world event date unknown'})
    active = {c['semantic_key'] for c in current['claims']}
    stale_count = 0
    for key, prior in old.items():
        if key not in active:
            retained = deepcopy(prior)
            retained['stale'] = True
            current['claims'].append(retained)
            stale_count += 1
            state = current['availability'][prior['family']]
            state['reason'] += '; last supported value retained as stale; removal not confirmed'
    # Prior evidence remains available for both sides of real changes and stale claims.
    for field, identifier in [('evidence', 'id'), ('source_snapshots', 'id')]:
        seen = {item[identifier] for item in current[field]}
        current[field].extend(deepcopy(item) for item in previous[field] if item[identifier] not in seen)
    current['refresh'] = {'previous_available': True, 'previous_profile_sha256': digest(previous), 'checked_at': now(), 'material_changes': len(current['changes']), 'retained_stale_claims': stale_count, 'removals_confirmed': 0, 'removal_policy': 'Disappearance or failed retrieval never confirms business deletion'}
    return current
