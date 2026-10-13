from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

from .extract import detect_conflicts, external_extract, html_document, identity_gate, next_sources, official_extract, summarize
from .fetch import BudgetExceeded, PolicyError, safe_url
from .models import Profile, now
from .refresh import apply_refresh

ENDPOINTS = {
    'legal_identity': 'https://data.brreg.no/enhetsregisteret/api/enheter/{org}',
    'financials': 'https://data.brreg.no/regnskapsregisteret/regnskap/{org}',
    'leadership': 'https://data.brreg.no/enhetsregisteret/api/enheter/{org}/roller',
    'locations': 'https://data.brreg.no/enhetsregisteret/api/underenheter?overordnetEnhet={org}&size=1000',
    'group': 'https://data.brreg.no/enhetsregisteret/api/konsernstruktur/{org}',
    'history_years': 'https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{org}/aar',
}


def fetch_official(p, module, broker, frozen=None):
    family = 'financial_history' if module == 'history_years' else module
    url = ENDPOINTS[module].format(org=p['organisation_number'])
    p['availability'][family]['attempted_sources'].append(url)
    try:
        if module == 'legal_identity' and frozen is not None:
            snapshot, body = frozen
        else:
            snapshot, raw = broker.fetch(url)
            p['source_snapshots'].append(snapshot)
            if snapshot['status'] != 200:
                state = 'not_available' if snapshot['status'] == 404 else 'blocked' if snapshot['status'] in (401, 403, 410, 429) else 'failed'
                p['availability'][family].update(state=state, reason='Source returned HTTP ' + str(snapshot['status']))
                if snapshot['status'] == 410:
                    p['errors'].append({'module': module, 'reason': 'Official legal removal: prior evidence must not be republished', 'legal_removal': True})
                return None
            body = json.loads(raw)
        if frozen is not None and module == 'legal_identity':
            p['source_snapshots'].append(snapshot)
        result = official_extract(p, module, body, snapshot)
        if not any(c['family'] == family for c in p['claims']):
            p['availability'][family].update(state='not_available', reason='Official source returned no usable records')
        return result
    except (ValueError, OSError, PolicyError, BudgetExceeded) as exc:
        p['availability'][family].update(state='blocked' if isinstance(exc, (PolicyError, BudgetExceeded)) else 'failed', reason=str(exc)[:250])
        p['errors'].append({'module': module, 'reason': str(exc)[:250]})
        return None


def baseline(org, broker, frozen=None):
    started = time.monotonic()
    p = Profile(organisation_number=org).model_dump(mode='json')
    if frozen is False:
        p['availability']['legal_identity'].update(state='failed', reason='Entity absent from supplied frozen registry')
        p['errors'].append({'module': 'legal_identity', 'reason': 'Entity absent from evaluator frozen registry'})
        return p
    entity = fetch_official(p, 'legal_identity', broker, frozen)
    # Do not attach external/financial data to an unanchored entity.
    if entity:
        for module in ('financials', 'leadership', 'locations', 'group'):
            fetch_official(p, module, broker)
        website = entity.get('hjemmeside')
        if website:
            p['candidate_ledger'].append({'url': website, 'source': 'official_registry', 'status': 'not_attempted', 'reason': 'Registry-listed candidate; ownership not yet established'})
    p['operations']['baseline_seconds'] = round(time.monotonic() - started, 3)
    return p


def enrich(p, broker, policy='gap', history=False):
    started = time.monotonic()
    if history and p.get('name'):
        fetch_official(p, 'history_years', broker)
    for candidate in p['candidate_ledger'][:1]:
        try:
            url = candidate['url']
            if not url.startswith(('https://', 'http://')): url = 'https://' + url
            url = safe_url(url)
            snapshot, raw = broker.fetch(url, 'company_owned')
            p['source_snapshots'].append(snapshot)
            if snapshot['status'] != 200:
                raise PolicyError('Company site unavailable: HTTP ' + str(snapshot['status']))
            document = html_document(raw, snapshot['final_url'])
            assessment = identity_gate(p['organisation_number'], p['name'], document, registry_linked=True)
            candidate.update(assessment)
            p['identity_links'].append({'type': 'candidate_website', 'from': p['organisation_number'], 'to': snapshot['final_url'], 'status': assessment['status'], 'snapshot_id': snapshot['id'], 'locator': assessment['locator'], 'reason': assessment['reason']})
            if not assessment['publishable']:
                p['availability']['website'].update(state='ambiguous', reason=assessment['reason'])
                # A home page can omit legal details. Inspect at most two observed
                # contact/legal links, but never transfer their proof to other pages.
                if not assessment['other_organisation_numbers'] and assessment['reason'] != 'Parked domain':
                    routes = next_sources(document, snapshot['final_url'], p['availability'], 'fixed', 500)
                    contacts = [r for r in routes if r['family'] == 'locations'][:2]
                    for route in contacts:
                        page, content = broker.fetch(route['url'], 'company_owned')
                        p['source_snapshots'].append(page)
                        if page['status'] != 200:
                            continue
                        parsed = html_document(content, page['final_url'])
                        proof = identity_gate(p['organisation_number'], p['name'], parsed, registry_linked=urlsplit(page['final_url']).hostname == urlsplit(snapshot['final_url']).hostname)
                        p['identity_links'].append({'type': 'candidate_contact_page', 'from': p['organisation_number'], 'to': page['final_url'], 'status': proof['status'], 'snapshot_id': page['id'], 'locator': proof['locator'], 'reason': proof['reason']})
                        p['decisions'].append({**route, 'purpose': 'exact_identity_verification', 'outcome': proof['status']})
                        external_extract(p, parsed, page, proof)
                        if proof['publishable']:
                            candidate.update(proof, verified_url=page['final_url'])
                            break
                continue
            external_extract(p, document, snapshot, assessment)
            for route in next_sources(document, snapshot['final_url'], p['availability'], policy):
                before = len(p['claims'])
                decision = {**route, 'request_reservation': 1, 'max_cost_usd': 0, 'max_response_bytes': 2_000_000, 'selected_at': now()}
                try:
                    page, content = broker.fetch(route['url'], 'company_owned')
                    p['source_snapshots'].append(page)
                    if page['status'] == 200:
                        parsed = html_document(content, page['final_url'])
                        proof = identity_gate(p['organisation_number'], p['name'], parsed, registry_linked=urlsplit(page['final_url']).hostname == urlsplit(url).hostname)
                        external_extract(p, parsed, page, proof)
                        decision['outcome'] = proof['status']
                    else:
                        decision['outcome'] = 'source_error'
                except (ValueError, OSError, BudgetExceeded) as exc:
                    decision['outcome'] = str(exc)[:160]
                decision['new_supported_claims'] = len(p['claims']) - before
                p['decisions'].append(decision)
        except (ValueError, OSError, BudgetExceeded) as exc:
            candidate.update(status='blocked' if isinstance(exc, PolicyError) else 'failed', reason=str(exc)[:250])
            p['availability']['website'].update(state=candidate['status'], reason=candidate['reason'])
    if not p['candidate_ledger']:
        p['availability']['website']['reason'] = 'No registry-listed website; paid/search discovery disabled'
    for family in ('company_profiles', 'jobs', 'public_activity', 'brand'):
        if p['availability'][family]['state'] != 'available':
            p['availability'][family].update(state='blocked' if p['candidate_ledger'] and p['availability']['website']['state'] == 'blocked' else 'not_available', reason='No permitted exact-entity source yielded this family; this is not proof of absence')
    p['operations']['enrichment_seconds'] = round(time.monotonic() - started, 3)
    return p


def finish(p, previous=None):
    if any(e.get('legal_removal') and e['module'] == 'legal_identity' for e in p['errors']):
        # Legal source removals take precedence over retention. No old identity gets republished.
        p['claims'] = []; p['evidence'] = []; p['name'] = None
        previous = None
    detect_conflicts(p)
    apply_refresh(p, previous)
    summarize(p)
    p['researched_at'] = now()
    for family, state in p['availability'].items():
        claims = [c for c in p['claims'] if c['family'] == family]
        state['accepted_claim_count'] = len([c for c in claims if c['availability'] == 'available' and not c['stale']])
        state['stale_claim_count'] = sum(c['stale'] for c in claims)
    Profile.model_validate(p)
    return p


def envelope(p, run_id, started_at):
    fresh = [c for c in p['claims'] if not c['stale'] and c['availability'] == 'available']
    status = 'completed' if p.get('name') and fresh else 'failed'
    return {'schema_version': 'aviscope-1', 'organisation_number': p['organisation_number'], 'run': {'run_id': run_id, 'started_at': started_at, 'completed_at': now(), 'terminal_status': status}, 'legal_identity': {'organisation_number': p['organisation_number'], 'name': p['name']}, 'claims': p['claims'], 'evidence': p['evidence'], 'availability': p['availability'], 'source_snapshots': p['source_snapshots'], 'refresh': p['refresh'], 'changes': p['changes'], 'errors': p['errors'], 'operations': p['operations']}
