from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .models import add_claim, digest


def norwegian_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = Decimal(str(value))
    else:
        text = str(value).strip().replace('\u00a0', '').replace(' ', '').replace('−', '-')
        if not text or text in ('-', '–', 'N/A'):
            return None
        negative = text.startswith('(') and text.endswith(')')
        text = text.strip('()')
        # Norwegian text uses a comma for decimals; period is a thousands separator.
        if ',' in text:
            text = text.replace('.', '').replace(',', '.')
        elif re.fullmatch(r'-?\d{1,3}(\.\d{3})+', text):
            text = text.replace('.', '')
        try:
            number = Decimal(text) * (-1 if negative else 1)
        except InvalidOperation:
            return None
    if not number.is_finite():
        return None
    return int(number) if number == number.to_integral() else float(number)


def pointer(value, path):
    for part in path.strip('/').split('/'):
        if path == '':
            return value
        part = part.replace('~1', '/').replace('~0', '~')
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, TypeError, ValueError):
            return None
    return value


def official_extract(p, module, body, snapshot):
    org = p['organisation_number']
    if module == 'legal_identity':
        if not isinstance(body, dict) or body.get('organisasjonsnummer') != org:
            raise ValueError('Registry response entity mismatch')
        p['name'] = body.get('navn')
        fields = {'legal_name': '/navn', 'legal_form': '/organisasjonsform/kode', 'industry': '/naeringskode1', 'registered_address': '/forretningsadresse', 'employees': '/antallAnsatte', 'bankrupt': '/konkurs', 'liquidating': '/underAvvikling', 'registered_purpose': '/vedtektsfestetFormaal', 'registered_activity': '/aktivitet', 'latest_filing_year': '/sisteInnsendteAarsregnskap', 'registration_date': '/registreringsdatoEnhetsregisteret'}
        for field, loc in fields.items():
            value = pointer(body, loc)
            if field == 'employees' and body.get('harRegistrertAntallAnsatte') is False:
                value = None
            add_claim(p, module, field, value, snapshot, loc)
        p['identity_links'].append({'type': 'official_registration', 'from': org, 'to': snapshot['final_url'], 'status': 'accepted', 'evidence_ids': [e['id'] for e in p['evidence']], 'reason': 'Exact legal organisation number'})
        return body
    if module == 'financials':
        if not isinstance(body, list):
            raise ValueError('Annual accounts response is not a list')
        paths = {
            'revenue': '/resultatregnskapResultat/driftsresultat/driftsinntekter/sumDriftsinntekter',
            'operating_result': '/resultatregnskapResultat/driftsresultat/driftsresultat',
            'profit_before_tax': '/resultatregnskapResultat/ordinaertResultatFoerSkattekostnad',
            'annual_result': '/resultatregnskapResultat/aarsresultat',
            'assets': '/eiendeler/sumEiendeler',
            'equity': '/egenkapitalGjeld/egenkapital/sumEgenkapital',
            'debt': '/egenkapitalGjeld/gjeldOversikt/sumGjeld',
        }
        for i, record in enumerate(body[:10]):
            if pointer(record, '/virksomhet/organisasjonsnummer') != org:
                raise ValueError('Annual accounts entity mismatch')
            scope = 'legal_entity' if record.get('regnskapstype') == 'SELSKAP' else 'group' if record.get('regnskapstype') == 'KONSERN' else 'unknown'
            period = record.get('regnskapsperiode')
            if scope == 'unknown' or not isinstance(period, dict) or not period.get('tilDato') or not record.get('valuta'):
                p['errors'].append({'module': module, 'reason': 'Accounts missing scope, period or currency; values withheld'})
                continue
            for field, loc in paths.items():
                raw = pointer(record, loc)
                # API numbers are numeric in currency units. No textual-unit inference.
                if raw is not None and (isinstance(raw, bool) or not isinstance(raw, (int, float))):
                    p['errors'].append({'module': module, 'field': field, 'reason': 'Unexpected nonnumeric API financial value'})
                    continue
                add_claim(p, module, field, norwegian_number(raw), snapshot, f'/{i}{loc}', period=period, currency=record['valuta'], unit='currency units (API numeric value)', scope=scope)
            add_claim(p, 'financial_history', 'available_account_record', {'record_id': record.get('id'), 'period': period, 'scope': scope}, snapshot, f'/{i}', key=record.get('id'), period=period, scope=scope)
    elif module == 'leadership':
        if not isinstance(body, dict):
            raise ValueError('Roles response must be an object')
        for i, group in enumerate(body.get('rollegrupper', [])):
            for j, role in enumerate(group.get('roller', [])):
                if role.get('avregistrert') or role.get('erSlettet'):
                    continue
                person_name = (role.get('person') or {}).get('navn') or {}
                name = ' '.join(str(person_name[k]) for k in ('fornavn', 'mellomnavn', 'etternavn') if person_name.get(k))
                if not name:
                    name = (role.get('enhet') or {}).get('navn')
                    if isinstance(name, list): name = ' '.join(name)
                if name:
                    value = {'name': name, 'role': (role.get('type') or {}).get('beskrivelse'), 'role_code': (role.get('type') or {}).get('kode')}
                    add_claim(p, module, 'registered_role', value, snapshot, f'/rollegrupper/{i}/roller/{j}', key=[name, value['role_code']], effective_at=group.get('sistEndret'))
    elif module == 'locations':
        if not isinstance(body, dict): raise ValueError('Locations response must be an object')
        for i, unit in enumerate(pointer(body, '/_embedded/underenheter') or []):
            if unit.get('overordnetEnhet') != org:
                p['errors'].append({'module': module, 'reason': 'Subunit parent mismatch; withheld'})
                continue
            if unit.get('slettedato'):
                continue
            value = {k: unit.get(k) for k in ('organisasjonsnummer', 'navn', 'beliggenhetsadresse', 'antallAnsatte')}
            add_claim(p, module, 'registered_workplace', value, snapshot, f'/_embedded/underenheter/{i}', key=unit.get('organisasjonsnummer'))
        if (body.get('page') or {}).get('totalPages', 1) > 1:
            p['errors'].append({'module': module, 'reason': 'Additional subunit pages remain unavailable under bounded first-page route'})
    elif module == 'group':
        # Retain group structure as explicitly scoped official relationship evidence.
        if body:
            add_claim(p, module, 'official_group_structure', body, snapshot, '', scope='group', identity_basis='Official group endpoint addressed by exact organisation number; group scope retained')
    elif module == 'history_years':
        if isinstance(body, list):
            years = [str(y) for y in body if re.fullmatch(r'\d{4}', str(y))]
            for i, year in enumerate(body):
                if str(year) in years:
                    add_claim(p, 'financial_history', 'available_filing_year', str(year), snapshot, f'/{i}', key=str(year))
    return body


def html_document(raw, url):
    soup = BeautifulSoup(raw, 'html.parser')
    structured = []
    for node in soup.select('script[type="application/ld+json"]')[:30]:
        try:
            obj = json.loads(node.string or node.get_text())
            structured.extend(obj if isinstance(obj, list) else [obj])
        except (ValueError, RecursionError):
            pass
    for node in soup(['script', 'style', 'noscript', 'template']):
        node.decompose()
    text = ' '.join(soup.stripped_strings)
    links = []
    for node in soup.select('a[href]')[:500]:
        target = urljoin(url, node.get('href', ''))
        if target.startswith(('http://', 'https://')):
            links.append({'url': target, 'text': node.get_text(' ', strip=True)[:200]})
    meta = soup.select_one('meta[name="description"]')
    return {'text': text, 'title': soup.title.get_text(' ', strip=True) if soup.title else '', 'description': meta.get('content') if meta else None, 'links': links, 'structured': structured}


def identity_gate(org, legal_name, document, *, registry_linked=False):
    text = document['text']
    # Match separate digits with limited separators, never concatenated unrelated numbers.
    pattern = r'(?<!\d)' + r'[ .\u00a0-]?'.join(org) + r'(?!\d)'
    match = re.search(pattern, text)
    found = set(re.findall(r'(?<!\d)(\d{3}[ .\u00a0-]?\d{3}[ .\u00a0-]?\d{3})(?!\d)', text))
    other = {re.sub(r'\D', '', x) for x in found} - {org}
    legal = re.sub(r'\s+', ' ', legal_name or '').casefold()
    name_match = bool(legal and legal in text.casefold())
    parked = any(x in text.lower() for x in ('domain is for sale', 'domain for sale', 'hugedomains', 'parked domain'))
    # Multiple legal identifiers may indicate a group or portfolio. Abstain, even when target appears.
    accepted = bool(match and name_match and registry_linked and not other and not parked)
    reason = 'Registry-listed domain, exact legal name and organisation number on page' if accepted else 'Insufficient exact-entity ownership evidence'
    if other: reason = 'Multiple company identifiers: shared/group ownership requires review'
    if parked: reason = 'Parked domain'
    return {'status': 'accepted' if accepted else 'ambiguous', 'publishable': accepted, 'reason': reason, 'organisation_number_present': bool(match), 'legal_name_present': name_match, 'other_organisation_numbers': sorted(other), 'locator': f'text:{match.start()}:{match.end()}' if match else None}


ROUTES = {'jobs': ('career', 'jobs', 'jobb', 'ledig', 'stilling', 'karriere'), 'public_activity': ('news', 'nyhet', 'aktuelt', 'press'), 'leadership': ('team', 'ledelse', 'ansatte', 'people'), 'locations': ('kontakt', 'contact', 'location', 'kontor'), 'brand': ('about', 'om-oss', 'om oss')}


def next_sources(document, url, coverage, policy='gap', limit=4):
    candidates = []
    seen = {url}
    for index, link in enumerate(document['links']):
        if link['url'] in seen or urlsplit(link['url']).hostname != urlsplit(url).hostname:
            continue
        seen.add(link['url'])
        text = (link['text'] + ' ' + link['url']).casefold()
        families = [f for f, words in ROUTES.items() if any(word in text for word in words)]
        if not families: continue
        missing = [f for f in families if coverage.get(f, {}).get('state') != 'available']
        score = sum({'jobs': 5, 'public_activity': 4, 'locations': 3, 'leadership': 2, 'brand': 1}[f] for f in missing)
        candidates.append({'url': link['url'], 'family': (missing or families)[0], 'score': score, 'source_order': index, 'reason': 'Observed same-domain link targeting an unresolved family', 'policy': policy})
    if policy == 'gap': candidates.sort(key=lambda c: (-c['score'], c['source_order']))
    return candidates[:limit]


def external_extract(p, document, snapshot, assessment):
    if not assessment['publishable']:
        return
    basis = assessment['reason']
    if not any(c['field'] == 'official_website' for c in p['claims']):
        add_claim(p, 'website', 'official_website', snapshot['final_url'], snapshot, assessment['locator'], identity_basis=basis)
    if document.get('description'):
        add_claim(p, 'brand', 'company_description', document['description'], snapshot, 'css:meta[name="description"]@content', identity_basis=basis)
    # JSON-LD facts require explicit entity matching. No arbitrary page text becomes a fact.
    queue = [(node, str(i)) for i, node in enumerate(document['structured'])]
    inspected = 0
    while queue and inspected < 100:
        node, location = queue.pop(0); inspected += 1
        if not isinstance(node, dict): continue
        if isinstance(node.get('@graph'), list):
            queue.extend((child, location + '/@graph/' + str(i)) for i, child in enumerate(node['@graph']))
        kind = node.get('@type')
        if kind == 'JobPosting':
            employer = node.get('hiringOrganization') or {}
            identifier = str(employer.get('taxID') or employer.get('identifier') or '')
            if re.sub(r'\D', '', identifier) != p['organisation_number']:
                continue
            if node.get('title') and node.get('datePosted'):
                value = {k: node.get(k) for k in ('title', 'datePosted', 'validThrough', 'employmentType', 'jobLocation', 'url')}
                add_claim(p, 'jobs', 'job_posting', value, snapshot, 'jsonld:/' + location, key=node.get('identifier') or [node['title'], node['datePosted']], effective_at=node['datePosted'], identity_basis='Exact taxID in hiringOrganization on verified company page')
        elif kind in ('NewsArticle', 'Article', 'BlogPosting'):
            about = node.get('about') or {}
            if isinstance(about, dict) and str(about.get('taxID') or about.get('identifier')) == p['organisation_number'] and node.get('headline') and node.get('datePublished'):
                add_claim(p, 'public_activity', 'company_article', {k: node.get(k) for k in ('headline', 'datePublished', 'url')}, snapshot, 'jsonld:/' + location, key=[node['headline'], node['datePublished']], effective_at=node['datePublished'], identity_basis='Exact organisation identifier in article subject')


def detect_conflicts(p):
    grouped = {}
    for claim in p['claims']:
        grouped.setdefault(claim['semantic_key'], []).append(claim)
    for key, claims in grouped.items():
        if len({digest(c['value']) for c in claims}) <= 1: continue
        ids = [c['id'] for c in claims]
        for claim in claims: claim['availability'] = 'ambiguous'
        p['review_queue'].append({'organisation_number': p['organisation_number'], 'field': claims[0]['field'], 'claim_ids': ids, 'reason': 'Conflicting supported values for the same entity, field, period and scope'})
        p['availability'][claims[0]['family']].update(state='ambiguous', reason='Conflicting supported claims require review')


def summarize(p):
    eligible = [c for c in p['claims'] if c['availability'] == 'available' and not c['stale'] and c['scope'] == 'legal_entity']
    facts = []
    for field in ('registered_activity', 'industry', 'employees', 'revenue', 'annual_result'):
        candidates = [c for c in eligible if c['field'] == field]
        if candidates:
            chosen = sorted(candidates, key=lambda c: (c.get('period') or {}).get('tilDato', ''), reverse=True)[0]
            facts.append({'field': field, 'value': chosen['value'], 'period': chosen.get('period'), 'currency': chosen.get('currency'), 'claim_id': chosen['id']})
    p['summary'] = {'title': p.get('name') or p['organisation_number'], 'facts': facts, 'unknowns': [k for k, v in p['availability'].items() if v['state'] != 'available'], 'changes_observed': len(p['changes']), 'method': 'Deterministic selection of supported, undisputed legal-entity claims; no model used'}
