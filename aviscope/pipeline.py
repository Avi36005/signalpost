from __future__ import annotations

import json
import socket
import time
from urllib.parse import urlsplit

from .extract import detect_conflicts, domain_labels, external_extract, keep_best_profiles, html_document, identity_gate, next_sources, official_extract, other_legal_names, shared_host, summarize
from .fetch import BudgetExceeded, PolicyError, safe_url
from .models import Profile, add_claim, now
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
        p['errors'].append({'module': module, 'reason': str(exc)[:250]})
        # A failed optional route never hides claims that another official route already supports.
        if not any(c['family'] == family for c in p['claims']):
            p['availability'][family].update(state='blocked' if isinstance(exc, (PolicyError, BudgetExceeded)) else 'failed', reason=str(exc)[:250])
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
        if isinstance(website, str) and website.strip():
            p['candidate_ledger'].append({'url': website.strip(), 'source': 'official_registry', 'status': 'not_attempted', 'reason': 'Registry-listed candidate; ownership not yet established'})
    p['operations']['baseline_seconds'] = round(time.monotonic() - started, 3)
    return p


GUESS_TLDS = ('.no', '.com')
HISTORY_MAX_WAIT = 20
MAX_GUESSES = 2


def resolves(host):
    """DNS-only existence check for a guessed domain; costs no HTTP request."""
    try:
        return bool(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM))
    except (OSError, UnicodeError):
        return False


def guessed_candidates(p):
    """Domains spelling the exact legal name. Candidates only: publication still needs page proof."""
    found = []
    for label in domain_labels(p.get('name'))[:4]:
        for tld in GUESS_TLDS:
            if len(found) >= MAX_GUESSES:
                break
            host = next((h for h in ('www.' + label + tld, label + tld) if resolves(h)), None)
            if host:
                found.append({'url': 'https://' + host + '/', 'source': 'name_derived_domain', 'status': 'not_attempted', 'reason': 'Domain spelling the exact legal name; ownership not yet established'})
    return found


def _bare_host(url):
    host = urlsplit(url if '://' in url else 'https://' + url).hostname or ''
    return host.removeprefix('www.')


def _probe(p, broker, url, registry_linked):
    """Fetch one candidate home page, then at most two same-host contact/about pages when the home page is inconclusive."""
    snapshot, raw = broker.fetch(url, 'company_owned')
    p['source_snapshots'].append(snapshot)
    if snapshot['status'] != 200:
        raise PolicyError('Company site unavailable: HTTP ' + str(snapshot['status']))
    host = urlsplit(snapshot['final_url']).hostname
    document = html_document(raw, snapshot['final_url'])
    assessment = identity_gate(p['organisation_number'], p['name'], document, registry_linked=registry_linked, host=host)
    p['identity_links'].append({'type': 'candidate_website', 'from': p['organisation_number'], 'to': snapshot['final_url'], 'status': assessment['status'], 'snapshot_id': snapshot['id'], 'locator': assessment['locator'], 'reason': assessment['reason']})
    if assessment['publishable'] and urlsplit(url).path.strip('/'):
        # A registry-declared section URL (ikm.no/ikm-lofteteknikk) is the entity's website, not the group root.
        assessment['website_url'] = snapshot['final_url']
    if assessment['publishable'] or assessment['other_organisation_numbers'] or assessment['reason'] in ('Parked domain',) or shared_host(host):
        return snapshot, document, assessment, None
    # A home page can omit legal details. Inspect at most two observed contact/legal links,
    # but never transfer their proof to other pages.
    routes = next_sources(document, snapshot['final_url'], p['availability'], 'fixed', 500)
    contacts = [r for r in routes if r['family'] in ('locations', 'brand')][:2]
    for route in contacts:
        try:
            page, content = broker.fetch(route['url'], 'company_owned')
        except (ValueError, OSError) as exc:
            p['decisions'].append({**route, 'purpose': 'exact_identity_verification', 'outcome': str(exc)[:160]})
            continue
        p['source_snapshots'].append(page)
        if page['status'] != 200:
            continue
        parsed = html_document(content, page['final_url'])
        same_host = urlsplit(page['final_url']).hostname == host
        proof = identity_gate(p['organisation_number'], p['name'], parsed, registry_linked=registry_linked and same_host, host=urlsplit(page['final_url']).hostname)
        p['identity_links'].append({'type': 'candidate_contact_page', 'from': p['organisation_number'], 'to': page['final_url'], 'status': proof['status'], 'snapshot_id': page['id'], 'locator': proof['locator'], 'reason': proof['reason']})
        p['decisions'].append({**route, 'purpose': 'exact_identity_verification', 'outcome': proof['status']})
        if proof['publishable'] and same_host:
            return page, parsed, proof, (snapshot, document)
    return snapshot, document, assessment, None


def enrich(p, broker, policy='gap', history=False, guess=True):
    started = time.monotonic()
    def attempts():
        yield from list(p['candidate_ledger'][:1 + MAX_GUESSES])
        # Reached only when no listed candidate verified (missing, dead, blocked or rejected):
        # fall back to name-spelled domains. They face the same gate; a spelling is a hint, not proof.
        if guess and p.get('name'):
            tried = {_bare_host(c['url']) for c in p['candidate_ledger']}
            fallback = [c for c in guessed_candidates(p) if _bare_host(c['url']) not in tried]
            if p['candidate_ledger']:
                for c in fallback: c['discovery'] = 'fallback after listed candidates failed verification'
            p['candidate_ledger'].extend(fallback)
            yield from fallback
    verified = None
    for candidate in attempts():
        try:
            url = candidate['url']
            if not url.startswith(('https://', 'http://')): url = 'https://' + url
            url = safe_url(url)
            registry_linked = candidate.get('source', 'official_registry') == 'official_registry'
            try:
                snapshot, document, assessment, home = _probe(p, broker, url, registry_linked)
            except PolicyError as exc:
                # Small company sites often serve plain HTTP only: refused connections and certificate
                # failures on HTTPS get one HTTP attempt at the same host. Identity gates are unchanged.
                if not url.startswith('https://') or not ('unreachable' in str(exc) or 'HTTP 0' in str(exc)):
                    raise
                url = 'http://' + url[len('https://'):]
                snapshot, document, assessment, home = _probe(p, broker, url, registry_linked)
            candidate.update(assessment)
            if not assessment['publishable']:
                candidate['status'] = 'ambiguous'
                continue
            if home:
                candidate['verified_url'] = snapshot['final_url']
            verified = (url, snapshot, document, assessment, home)
            break
        except (ValueError, OSError, BudgetExceeded) as exc:
            candidate.update(status='blocked' if isinstance(exc, (PolicyError, BudgetExceeded)) else 'failed', reason=str(exc)[:250])
            if isinstance(exc, BudgetExceeded):
                break
    if verified:
        url, snapshot, document, assessment, home = verified
        external_extract(p, document, snapshot, assessment)
        if home:
            # The contact page proved the host. The home page's own description may be cited from
            # the home snapshot, but only when that page carries no other identifier, names no other
            # legal entity and is not parked; the identity basis names the proving page.
            home_snapshot, document = home
            check = identity_gate(p['organisation_number'], p['name'], document, host=urlsplit(home_snapshot['final_url']).hostname)
            if (document.get('description') and urlsplit(home_snapshot['final_url']).hostname == urlsplit(snapshot['final_url']).hostname
                    and not check['other_organisation_numbers'] and check['reason'] != 'Parked domain'
                    and not other_legal_names(document['text'], p['name'])
                    and not any(c['field'] == 'company_description' for c in p['claims'])):
                add_claim(p, 'brand', 'company_description', document['description'], home_snapshot, 'css:meta[name="description"]@content',
                          identity_basis=f'Home page of a host whose ownership was proven on {snapshot["final_url"]} ({assessment["reason"]}); text cited from the home page')
        crawl_host = urlsplit(snapshot['final_url']).hostname
        for route in next_sources(document, home[0]['final_url'] if home else snapshot['final_url'], p['availability'], policy, 5):
            if route['url'] == snapshot['final_url']:
                continue
            before = len(p['claims'])
            decision = {**route, 'request_reservation': 1, 'max_cost_usd': 0, 'max_response_bytes': 2_000_000, 'selected_at': now()}
            try:
                page, content = broker.fetch(route['url'], 'company_owned')
                p['source_snapshots'].append(page)
                if page['status'] == 200 and urlsplit(page['final_url']).hostname == crawl_host:
                    parsed = html_document(content, page['final_url'])
                    proof = identity_gate(p['organisation_number'], p['name'], parsed, registry_linked=True, host=crawl_host)
                    if not proof['publishable'] and not proof['other_organisation_numbers'] and proof['reason'] != 'Parked domain':
                        # Same verified host: the page inherits host-level ownership, not page-level proof.
                        proof = {**assessment, 'reason': 'Page on verified company host (' + assessment['reason'] + ')', 'locator': assessment['locator']}
                        external_extract(p, {**parsed, 'description': None}, page, proof)
                    else:
                        external_extract(p, parsed, page, proof)
                    decision['outcome'] = proof['status']
                else:
                    decision['outcome'] = 'source_error' if page['status'] != 200 else 'left_verified_host'
            except (ValueError, OSError, BudgetExceeded) as exc:
                decision['outcome'] = str(exc)[:160]
            decision['new_supported_claims'] = len(p['claims']) - before
            p['decisions'].append(decision)
        keep_best_profiles(p)
    elif p['candidate_ledger']:
        states = [c.get('status') for c in p['candidate_ledger']]
        state = 'ambiguous' if 'ambiguous' in states else 'blocked' if 'blocked' in states else 'failed'
        reasons = '; '.join(sorted({c.get('reason', '') for c in p['candidate_ledger'] if c.get('reason')}))[:250]
        p['availability']['website'].update(state=state, reason=reasons or 'No candidate passed the exact-entity gate')
    if history and p.get('name'):
        # Filing-year discovery is rate limited (one start per 2.1 s). It runs after website work and
        # is skipped when its queue is long, so it can never starve other companies' research.
        if broker.slot_delay('data.brreg.no#filing-copy') <= HISTORY_MAX_WAIT:
            fetch_official(p, 'history_years', broker)
        else:
            p['decisions'].append({'route': 'history_years', 'outcome': 'skipped', 'reason': 'Rate-limited filing-year queue exceeded ' + str(HISTORY_MAX_WAIT) + ' s; account records remain available'})
    if not p['candidate_ledger']:
        p['availability']['website']['reason'] = 'No registry-listed website and no resolvable domain spelling the legal name; paid search discovery disabled'
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
    return {'schema_version': 'aviscope-1', 'organisation_number': p['organisation_number'], 'run': {'run_id': run_id, 'started_at': started_at, 'completed_at': now(), 'terminal_status': status}, 'legal_identity': {'organisation_number': p['organisation_number'], 'name': p['name']}, 'summary': p.get('summary', {}), 'claims': p['claims'], 'evidence': p['evidence'], 'availability': p['availability'], 'source_snapshots': p['source_snapshots'], 'refresh': p['refresh'], 'changes': p['changes'], 'errors': p['errors'], 'operations': p['operations']}
