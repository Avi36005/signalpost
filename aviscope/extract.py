from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .models import add_claim, digest, org_number


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
        fields = {'legal_name': '/navn', 'legal_form': '/organisasjonsform/kode', 'industry': '/naeringskode1', 'registered_address': '/forretningsadresse', 'employees': '/antallAnsatte', 'bankrupt': '/konkurs', 'liquidating': '/underAvvikling', 'registered_purpose': '/vedtektsfestetFormaal', 'registered_activity': '/aktivitet', 'latest_filing_year': '/sisteInnsendteAarsregnskap', 'registration_date': '/registreringsdatoEnhetsregisteret', 'registered_homepage': '/hjemmeside'}
        for field, loc in fields.items():
            if loc is None:
                continue
            value = pointer(body, loc)
            if field == 'employees' and body.get('harRegistrertAntallAnsatte') is False:
                value = None
            add_claim(p, module, field, value, snapshot, loc)
        # The registered business address is the entity's official head-office location.
        address = body.get('forretningsadresse')
        if isinstance(address, dict) and (address.get('adresse') or address.get('poststed')):
            add_claim(p, 'locations', 'head_office_address', body['forretningsadresse'], snapshot, '/forretningsadresse', key='head_office')
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
    meta = soup.select_one('meta[name="description"]')
    site = soup.select_one('meta[property="og:site_name"]')
    for node in soup(['script', 'style', 'noscript', 'template']):
        node.decompose()
    text = ' '.join(soup.stripped_strings)
    links = []
    for node in soup.select('a[href]')[:500]:
        target = urljoin(url, node.get('href', ''))
        if target.startswith(('http://', 'https://')):
            links.append({'url': target, 'text': node.get_text(' ', strip=True)[:200]})
    return {'text': text, 'title': soup.title.get_text(' ', strip=True) if soup.title else '', 'description': meta.get('content') if meta else None, 'site_name': (site.get('content') or '').strip() or None if site else None, 'links': links, 'structured': structured}


LEGAL_SUFFIX = re.compile(r'\s+(AS|ASA|SA|DA|ANS|NUF|BA|BRL|STI|KF|IKS|SF|ENK)\.?$', re.I)
AMBIGUOUS_SUFFIXES = ('AS', 'SA', 'DA', 'BA')
SHARED_HOSTS = ('obos.no', 'usbl.no', 'bate.no', 'tobb.no', 'boligbyggelag.no', 'mallofnorway.com', 'visma.com', 'wix.com', 'wixsite.com', 'squarespace.com', 'webnode.page', 'blogspot.com', 'wordpress.com', 'github.io', 'proff.no', 'gulesider.no', '1881.no', 'purehelp.no', 'brreg.no')


def name_core(legal_name):
    return LEGAL_SUFFIX.sub('', re.sub(r'\s+', ' ', legal_name or '').strip())


def domain_labels(legal_name):
    """Registrable-label spellings a company's own domain commonly uses for its exact legal name."""
    core = name_core(legal_name).casefold().replace('&', ' og ').replace('+', ' og ')
    tokens = [t for t in re.split(r'[^0-9a-zæøåäöü]+', core) if t]
    if not tokens:
        return []
    variants = []
    for parts in (tokens, [t for t in tokens if t not in ('og', 'and')]):
        for joiner in ('', '-'):
            label = joiner.join(parts)
            variants += [label, label.replace('æ', 'ae').replace('ø', 'o').replace('å', 'a').replace('ä', 'a').replace('ö', 'o').replace('ü', 'u'),
                         label.replace('æ', 'ae').replace('ø', 'oe').replace('å', 'aa')]
    return [v for v in dict.fromkeys(variants) if 3 <= len(v) <= 63 and not v.startswith('-')]


def registrable_label(host):
    parts = (host or '').lower().rstrip('.').split('.')
    if parts and parts[0] == 'www':
        parts = parts[1:]
    if len(parts) >= 3 and '.'.join(parts[-2:]) in ('co.uk', 'com.au'):
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else (parts[0] if parts else '')


def domain_matches_name(host, legal_name):
    label = registrable_label(host)
    try:
        label = label.encode('ascii').decode('idna') if label.startswith('xn--') else label
    except UnicodeError:
        pass
    return bool(label) and label in domain_labels(legal_name)


def shared_host(host):
    host = (host or '').lower()
    return any(host == x or host.endswith('.' + x) for x in SHARED_HOSTS)


PORTFOLIO_WORDS = ('portfolio', 'portefølje', 'våre selskaper', 'our companies', 'investeringer', 'investments', 'datterselskap', 'subsidiaries', 'konsernet', 'referanser', 'våre kunder', 'our clients', 'our customers')
OTHER_LEGAL_NAME = re.compile(r'(?<![\w])([A-ZÆØÅ0-9][\wÆØÅæøå&.\-]*(?: [\wÆØÅæøå&.\-]+){0,5}?) (AS|ASA|AB|ApS|A/S|Oy|Oyj|GmbH|Ltd|LLC|Inc|BV|SA)(?![\w])')


def other_legal_names(text, legal_name):
    target = re.sub(r'\s+', ' ', legal_name or '').casefold()
    names = {re.sub(r'\s+', ' ', m.group(0)).casefold() for m in OTHER_LEGAL_NAME.finditer(text)}
    return {n for n in names if n != target and not target.endswith(n) and not n.endswith(target)}


def legal_name_span(text, legal_name):
    """Whole-word occurrence of the exact legal name. The name body may differ in case, but a legal
    suffix must be written as a suffix ("Drag AS", not "drag as needed")."""
    legal = re.sub(r'\s+', ' ', legal_name or '').strip()
    if not legal:
        return None
    suffix = LEGAL_SUFFIX.search(legal)
    body = legal[:suffix.start()] if suffix else legal
    words = [re.escape(w) for w in body.split(' ') if w]
    if not words:
        return None
    pattern = r'(?<![\w])(?i:' + r'\s+'.join(words) + r')' + (r'\s+' + re.escape(suffix.group(1).upper()) + r'\.?' if suffix else '') + r'(?![\w])'
    for match in re.finditer(pattern, text):
        # Suffixes that are also ordinary words ("as", "da", "sa") are ambiguous in all-caps text:
        # "FOLLOW AMALIE AS WE TRAVEL" is a sentence, not the legal name AMALIE AS.
        if suffix and suffix.group(1).upper() in AMBIGUOUS_SUFFIXES and re.match(r'\s+[A-ZÆØÅÄÖÜ]+(?![\w.])', text[match.end():]):
            continue
        return (match.start(), match.end())
    return None


def valid_org_numbers(text):
    found = set()
    for raw in re.findall(r'(?<!\d)(\d{3}[ .\u00a0-]?\d{3}[ .\u00a0-]?\d{3})(?!\d)', text):
        candidate = re.sub(r'\D', '', raw)
        try:
            found.add(org_number(candidate))
        except ValueError:
            pass
    return found


def identity_gate(org, legal_name, document, *, registry_linked=False, host=None):
    """Exact-entity gate. Tiers, strongest first:
    1. the target organisation number on the page (any candidate source);
    2. a registry-declared homepage that shows the exact legal name;
    3. a registry-declared homepage whose own domain spells the exact legal name.
    A guessed (non-registry) domain needs tier 1, or the exact legal name together with a
    name-spelling domain. Any other checksum-valid organisation number, a parked page or a
    known shared portal keeps the candidate ambiguous."""
    text = document['text']
    # Match separate digits with limited separators, never concatenated unrelated numbers.
    pattern = r'(?<!\d)' + r'[ .\u00a0-]?'.join(org) + r'(?!\d)'
    match = re.search(pattern, text)
    other = valid_org_numbers(text) - {org}
    legal = re.sub(r'\s+', ' ', legal_name or '').strip()
    name_hit = legal_name_span(text, legal)
    name_at = name_hit[0] if name_hit else -1
    name_match = name_hit is not None
    if name_hit: legal = text[name_hit[0]:name_hit[1]]
    parked = any(x in text.lower() for x in ('domain is for sale', 'domain for sale', 'hugedomains', 'parked domain', 'domenet er til salgs', 'this domain may be for sale'))
    domain_match = bool(host) and domain_matches_name(host, legal_name)
    shared = bool(host) and shared_host(host)
    # Without the organisation number, a page naming other legal entities or describing a
    # portfolio/group may be a parent's or investor's site: never publish on name alone there.
    named_others = other_legal_names(text, legal_name)
    name_only_risky = not match and (bool(named_others) or any(w in text.casefold() for w in PORTFOLIO_WORDS))
    # The number under another entity's name (franchise, client list) is not ownership proof.
    number_contradicted = bool(match) and not name_match and bool(named_others)
    locator, basis = None, None
    if match and not number_contradicted and (registry_linked or name_match or domain_match):
        locator, basis = f'text:{match.start()}:{match.end()}', ('Registry-listed domain; exact organisation number on page' if registry_linked else 'Exact organisation number on a domain spelling the legal name' if domain_match else 'Exact organisation number and legal name on candidate page')
    elif registry_linked and name_match and not name_only_risky:
        locator, basis = f'text:{name_at}:{name_at + len(legal)}', 'Registry-listed domain; exact legal name on page'
    elif registry_linked and domain_match:
        locator, basis = 'host:' + host, 'Registry-listed domain spells the exact legal name'
    elif domain_match and name_match and not name_only_risky:
        locator, basis = f'text:{name_at}:{name_at + len(legal)}', 'Domain spells the exact legal name and page shows the exact legal name'
    accepted = bool(basis) and not other and not parked and not shared
    reason = basis if accepted else 'Insufficient exact-entity ownership evidence'
    if other: reason = 'Multiple company identifiers: shared/group ownership requires review'
    if shared: reason = 'Shared portal or platform domain; not exclusively owned by this entity'
    if parked: reason = 'Parked domain'
    return {'status': 'accepted' if accepted else 'ambiguous', 'publishable': accepted, 'reason': reason, 'organisation_number_present': bool(match), 'legal_name_present': name_match, 'domain_matches_name': domain_match, 'other_organisation_numbers': sorted(other), 'locator': locator if accepted else (f'text:{match.start()}:{match.end()}' if match else None)}


ROUTES = {'jobs': ('career', 'jobs', 'jobb', 'ledig', 'stilling', 'karriere', 'rekrutt', 'vacanc'), 'public_activity': ('news', 'nyhet', 'aktuelt', 'press', 'blogg', 'blog', 'artikl'), 'leadership': ('team', 'ledelse', 'ansatte', 'people'), 'locations': ('kontakt', 'contact', 'location', 'kontor', 'avdeling'), 'brand': ('about', 'om-oss', 'om oss', '/om/', 'om-selskapet', 'om-firma', 'personvern', 'privacy', 'vilkar', 'vilkår', 'terms')}


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


SOCIAL = {'facebook.com': 'facebook', 'instagram.com': 'instagram', 'linkedin.com': 'linkedin', 'x.com': 'x', 'twitter.com': 'x', 'youtube.com': 'youtube', 'tiktok.com': 'tiktok', 'vimeo.com': 'vimeo', 'pinterest.com': 'pinterest', 'github.com': 'github'}
NOT_PROFILE = ('sharer', 'share', 'intent', 'dialog', 'plugins', 'login', 'signup', 'hashtag', 'search', 'watch', 'embed', 'policy', 'privacy', 'legal', 'help', 'about', 'home', 'p', 'tr')


def social_profile(url):
    """Canonical company profile URL for a known platform, or None for share/intent/content links."""
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    platform = next((name for domain, name in SOCIAL.items() if host == domain or host.endswith('.' + domain)), None)
    segments = [x for x in parts.path.split('/') if x]
    if not platform or not segments or segments[0].lower() in NOT_PROFILE or parts.query.lower().startswith(('u=', 'url=', 'text=')):
        return None
    if platform == 'linkedin' and (segments[0] not in ('company', 'school', 'showcase') or len(segments) < 2):
        return None
    if platform == 'youtube' and not (segments[0].startswith('@') or segments[0] in ('channel', 'c', 'user')):
        return None
    if platform in ('facebook', 'instagram', 'x', 'tiktok') and (len(segments) > 2 or segments[0].lower() in ('pages', 'groups', 'events', 'reel', 'reels', 'stories', 'status', 'i')):
        if not (platform == 'facebook' and segments[0] == 'pages'):
            return None
    keep = segments[:2] if platform in ('linkedin', 'youtube') and segments[0] in ('company', 'school', 'showcase', 'channel', 'c', 'user') else segments[:1]
    if platform == 'facebook' and segments[0] == 'pages':
        keep = segments[:3]
    return {'platform': platform, 'url': f'https://{host.removeprefix("m.").removeprefix("www.") if platform != "linkedin" else "www.linkedin.com"}/' + '/'.join(keep)}


def site_root(url):
    parts = urlsplit(url)
    return f'{parts.scheme}://{parts.hostname}/'


def _squash(value):
    return re.sub(r'[^0-9a-z]', '', str(value or '').casefold().replace('æ', 'ae').replace('ø', 'o').replace('å', 'a'))


def profile_belongs(handle_url, p, host):
    """A linked profile must be recognisably this company's: its handle spells (part of) the legal
    name, brand or domain. Site-builder footers (facebook.com/wix) and personal pages are rejected."""
    path = [x for x in urlsplit(handle_url).path.split('/') if x]
    handle = _squash(path[-1].lstrip('@') if path else '')
    if len(handle) < 3:
        return False
    names = [name_core(p.get('name')), registrable_label(host)] + [str(c['value']) for c in p['claims'] if c['field'] == 'public_brand_name']
    for name in names:
        whole = _squash(name)
        if len(whole) >= 3 and (whole in handle or handle in whole):
            return True
        if any(len(token) >= 5 and _squash(token) in handle for token in re.split(r'[\s&+.,-]+', name or '')):
            return True
    return False


def profile_fit(handle_url, p, host):
    """Lower is better: 0 when the handle is exactly the squashed name, brand or domain label."""
    path = [x for x in urlsplit(handle_url).path.split('/') if x]
    handle = _squash(path[-1].lstrip('@') if path else '')
    names = [_squash(x) for x in [name_core(p.get('name')), registrable_label(host)] + [str(c['value']) for c in p['claims'] if c['field'] == 'public_brand_name']]
    return min((abs(len(handle) - len(n)) for n in names if n and (n in handle or handle in n)), default=99)


def keep_best_profiles(p):
    """One linked profile per platform: the handle that most closely spells the company. Surname pages
    of employees (vibekeholtskog for HOLTSKOG AS) lose to the company's own handle."""
    best = {}
    hosts = {e['id']: urlsplit(e['source_url']).hostname for e in p['evidence']}
    for c in p['claims']:
        if c['field'] == 'linked_profile':
            score = profile_fit(c['value']['url'], p, hosts.get(c['evidence_ids'][0]))
            platform = c['value']['platform']
            if platform not in best or score < best[platform][0]:
                best[platform] = (score, c['id'])
    keep = {cid for _, cid in best.values()}
    p['claims'] = [c for c in p['claims'] if c['field'] != 'linked_profile' or c['id'] in keep]


def _employer_conflicts(employer, p):
    """True when structured employer/subject data names a different legal entity."""
    if not isinstance(employer, dict):
        return False
    identifier = re.sub(r'\D', '', str(employer.get('taxID') or employer.get('vatID') or employer.get('identifier') or ''))
    if identifier:
        return identifier[-9:] != p['organisation_number']
    name = str(employer.get('name') or '').strip()
    if not name:
        return False
    known = {name_core(p.get('name')).casefold()} | {str(c['value']).casefold() for c in p['claims'] if c['field'] == 'public_brand_name'}
    return name_core(name).casefold() not in known


def _schema_date(value):
    """A schema.org Date or DateTime as an aware UTC datetime; None when malformed."""
    if not isinstance(value, str) or not re.match(r'\d{4}-\d{2}-\d{2}', value.strip()):
        return None
    text = value.strip().replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(text) if 'T' in text else datetime.fromisoformat(text[:10])
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def job_dates_status(node, evaluated_at):
    """'current' for a posting that is open at the evaluation time (the page's retrieval time).
    Expired, not-yet-posted and malformed dates are withheld rather than published as hiring."""
    at = _schema_date(evaluated_at)
    posted = _schema_date(node.get('datePosted'))
    if posted is None or at is None:
        return 'malformed datePosted'
    if posted > at + timedelta(days=1):
        return 'datePosted after evaluation time'
    if node.get('validThrough') in (None, ''):
        return 'current'
    until = _schema_date(node.get('validThrough'))
    if until is None:
        return 'malformed validThrough'
    # A date-only validThrough is open through the whole of that day.
    if 'T' not in str(node['validThrough']):
        until += timedelta(days=1)
    return 'current' if until > at else 'expired before evaluation time'


def external_extract(p, document, snapshot, assessment):
    if not assessment['publishable']:
        return
    basis = assessment['reason']
    if not any(c['field'] == 'official_website' for c in p['claims']):
        add_claim(p, 'website', 'official_website', assessment.get('website_url') or site_root(snapshot['final_url']), snapshot, assessment['locator'], identity_basis=basis)
    on_site = 'Published on the verified company website (' + basis + ')'
    host = urlsplit(snapshot['final_url']).hostname
    # One company description per profile: further pages describe pages, not the company.
    if document.get('description') and not any(c['field'] == 'company_description' for c in p['claims']):
        add_claim(p, 'brand', 'company_description', document['description'], snapshot, 'css:meta[name="description"]@content', identity_basis=basis)
    if document.get('site_name') and not any(c['field'] == 'public_brand_name' for c in p['claims']):
        add_claim(p, 'brand', 'public_brand_name', document['site_name'], snapshot, 'css:meta[property="og:site_name"]@content', key='site_name', identity_basis=on_site)
    seen = {c['value']['url'] for c in p['claims'] if c['field'] == 'linked_profile'}
    for index, link in enumerate(document.get('links', [])):
        profile = social_profile(link['url'])
        if profile and profile['url'] not in seen and profile_belongs(profile['url'], p, host):
            seen.add(profile['url'])
            add_claim(p, 'company_profiles', 'linked_profile', {**profile, 'href': link['url']}, snapshot, f'link:{index}', key=profile['url'], identity_basis='Profile linked from the verified company website; destination not fetched')
    # JSON-LD facts require explicit entity matching. No arbitrary page text becomes a fact.
    queue = [(node, str(i)) for i, node in enumerate(document['structured'])]
    inspected = 0
    while queue and inspected < 200:
        node, location = queue.pop(0); inspected += 1
        if not isinstance(node, dict): continue
        if isinstance(node.get('@graph'), list):
            queue.extend((child, location + '/@graph/' + str(i)) for i, child in enumerate(node['@graph']))
        if isinstance(node.get('itemListElement'), list):
            queue.extend((child.get('item', child) if isinstance(child, dict) else child, location + '/itemListElement/' + str(i) + ('/item' if isinstance(child, dict) and isinstance(child.get('item'), dict) else '')) for i, child in enumerate(node['itemListElement']))
        kind = node.get('@type')
        kinds = kind if isinstance(kind, list) else [kind]
        if 'JobPosting' in kinds:
            employer = node.get('hiringOrganization') or {}
            exact = isinstance(employer, dict) and re.sub(r'\D', '', str(employer.get('taxID') or employer.get('identifier') or ''))[-9:] == p['organisation_number']
            if _employer_conflicts(employer, p):
                continue
            if node.get('title') and node.get('datePosted'):
                status = job_dates_status(node, snapshot['retrieved_at'])
                if status != 'current':
                    p['decisions'].append({'route': 'jobs', 'url': snapshot['final_url'], 'outcome': 'job_withheld', 'reason': status, 'title': str(node['title'])[:120], 'datePosted': str(node['datePosted'])[:40], 'validThrough': str(node.get('validThrough'))[:40], 'evaluated_at': snapshot['retrieved_at']})
                    continue
                value = {k: node.get(k) for k in ('title', 'datePosted', 'validThrough', 'employmentType', 'jobLocation', 'url')}
                add_claim(p, 'jobs', 'job_posting', value, snapshot, 'jsonld:/' + location, key=node.get('identifier') if isinstance(node.get('identifier'), str) else [node['title'], node['datePosted']], effective_at=str(node['datePosted']), identity_basis='Exact taxID in hiringOrganization on verified company page' if exact else on_site + '; employer not a different entity')
        elif set(kinds) & {'NewsArticle', 'Article', 'BlogPosting', 'PressRelease'}:
            if _employer_conflicts(node.get('about') or {}, p) or _employer_conflicts(node.get('publisher') or {}, p):
                continue
            if node.get('headline') and node.get('datePublished'):
                add_claim(p, 'public_activity', 'company_article', {k: node.get(k) for k in ('headline', 'datePublished', 'url')}, snapshot, 'jsonld:/' + location, key=[node['headline'], node['datePublished']], effective_at=str(node['datePublished']), identity_basis=on_site)
        elif set(kinds) & {'Organization', 'Corporation', 'LocalBusiness', 'Store', 'Restaurant', 'ProfessionalService'}:
            if _employer_conflicts({k: node.get(k) for k in ('taxID', 'vatID', 'identifier')}, p):
                continue
            same = node.get('sameAs')
            for j, url in enumerate(same if isinstance(same, list) else [same] if isinstance(same, str) else []):
                profile = social_profile(url) if isinstance(url, str) else None
                if profile and profile['url'] not in seen and profile_belongs(profile['url'], p, host):
                    seen.add(profile['url'])
                    add_claim(p, 'company_profiles', 'linked_profile', {**profile, 'href': url}, snapshot, 'jsonld:/' + location + '/sameAs' + ('/' + str(j) if isinstance(same, list) else ''), key=profile['url'], identity_basis='Profile declared in verified company website structured data; destination not fetched')


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


LEGAL_FORMS = {'AS': 'private limited company', 'ASA': 'public limited company', 'ENK': 'sole proprietorship', 'NUF': 'Norwegian branch of a foreign company', 'DA': 'partnership with shared liability', 'ANS': 'general partnership', 'SA': 'cooperative', 'STI': 'foundation', 'BRL': 'housing cooperative', 'ESEK': 'owner-section condominium', 'FLI': 'association', 'KF': 'municipal enterprise', 'IKS': 'inter-municipal company', 'SF': 'state enterprise'}
LEAD_ROLES = ('DAGL', 'LEDE', 'KONT', 'DTPR', 'DTSO')


def _money(value, currency):
    if not isinstance(value, (int, float)):
        return str(value)
    sign = '-' if value < 0 else ''
    value = abs(value)
    if value >= 1_000_000:
        text = f'{value / 1_000_000:,.1f} million'
    else:
        text = f'{value:,.0f}'
    return f'{currency or ""} {sign}{text}'.strip()


def summarize(p):
    """Deterministic, cited narrative. Every sentence lists the claim ids it rests on; nothing is
    inferred beyond the supported, undisputed, current legal-entity claims."""
    eligible = [c for c in p['claims'] if c['availability'] == 'available' and not c['stale']]
    entity = [c for c in eligible if c['scope'] == 'legal_entity']
    def first(field, pool=entity):
        found = [c for c in pool if c['field'] == field]
        return sorted(found, key=lambda c: (c.get('period') or {}).get('tilDato', ''), reverse=True)[0] if found else None
    facts = []
    for field in ('legal_form', 'registered_activity', 'industry', 'employees', 'revenue', 'operating_result', 'annual_result', 'head_office_address', 'official_website', 'company_description', 'public_brand_name'):
        chosen = first(field)
        if chosen:
            facts.append({'field': field, 'value': chosen['value'], 'period': chosen.get('period'), 'currency': chosen.get('currency'), 'scope': chosen['scope'], 'claim_id': chosen['id']})
    for field, limit in (('registered_role', 6), ('job_posting', 5), ('company_article', 3), ('linked_profile', 6)):
        chosen = sorted((c for c in entity if c['field'] == field and (field != 'registered_role' or (isinstance(c['value'], dict) and c['value'].get('role_code') in LEAD_ROLES))), key=lambda c: str(c.get('effective_at') or ''), reverse=True)[:limit]
        facts += [{'field': field, 'value': c['value'], 'effective_at': c.get('effective_at'), 'scope': c['scope'], 'claim_id': c['id']} for c in chosen]
    name = p.get('name') or p['organisation_number']
    narrative = []
    def say(text, *claims):
        ids = [c['id'] for c in claims if c]
        if ids:
            narrative.append({'text': text, 'claim_ids': ids})
    form, industry, activity, registered = first('legal_form'), first('industry'), first('registered_activity'), first('registration_date')
    if form or industry:
        kind = LEGAL_FORMS.get(form['value'], form['value']) if form else 'entity'
        sector = industry['value'].get('beskrivelse') if industry and isinstance(industry['value'], dict) else None
        say(f'{name} is a Norwegian {kind}' + (f' in "{sector}"' if sector else '') + (f', registered {registered["value"]}' if registered else '') + '.', form, industry, registered)
    if activity:
        text = activity['value'] if isinstance(activity['value'], str) else ' '.join(map(str, activity['value'])) if isinstance(activity['value'], list) else str(activity['value'])
        say(f'Registered activity: {text.strip()}', activity)
    description = first('company_description')
    if description:
        say(f'Its own website describes it as: "{str(description["value"]).strip()[:300]}"', description)
    revenue, result, employees = first('revenue'), first('annual_result'), first('employees')
    if revenue or result:
        period = ((revenue or result).get('period') or {}).get('tilDato', '')[:4]
        parts = ([f'revenue of {_money(revenue["value"], revenue.get("currency"))}'] if revenue else []) + ([f'an annual result of {_money(result["value"], result.get("currency"))}'] if result else [])
        say(f'Latest filed legal-entity accounts{" for " + period if period else ""} show ' + ' and '.join(parts) + '.', revenue, result)
    if employees:
        say(f'The registry lists {employees["value"]} employees.', employees)
    if first('bankrupt') and first('bankrupt')['value'] is True:
        say('The registry marks the entity as bankrupt.', first('bankrupt'))
    if first('liquidating') and first('liquidating')['value'] is True:
        say('The registry marks the entity as being wound up.', first('liquidating'))
    leaders = [c for c in entity if c['field'] == 'registered_role' and isinstance(c['value'], dict) and c['value'].get('role_code') in LEAD_ROLES]
    if leaders:
        say('Registered leadership: ' + '; '.join(f'{c["value"]["name"]} ({c["value"]["role"]})' for c in leaders[:4]) + '.', *leaders[:4])
    office, workplaces = first('head_office_address'), [c for c in entity if c['field'] == 'registered_workplace']
    if office or workplaces:
        city = office['value'].get('poststed') if office and isinstance(office['value'], dict) else None
        say((f'Head office in {city.title()}' if city else 'Registered head office on file') + (f', with {len(workplaces)} registered workplace{"s" if len(workplaces) != 1 else ""}' if workplaces else '') + '.', office, *workplaces[:3])
    website = first('official_website')
    profiles = [c for c in entity if c['field'] == 'linked_profile']
    if website:
        say(f'Verified website: {website["value"]}' + (f'; it links to {", ".join(sorted({c["value"]["platform"] for c in profiles}))} profiles' if profiles else '') + '.', website, *profiles)
    jobs = [c for c in entity if c['family'] == 'jobs']
    if jobs:
        say(f'{len(jobs)} dated job posting{"s" if len(jobs) != 1 else ""} found on company-owned pages.', *jobs[:5])
    articles = sorted([c for c in entity if c['family'] == 'public_activity'], key=lambda c: str(c.get('effective_at') or ''), reverse=True)
    if articles:
        say(f'Latest dated company publication: "{articles[0]["value"].get("headline")}" ({str(articles[0]["value"].get("datePublished"))[:10]}).', articles[0])
    if p['changes']:
        narrative.append({'text': f'{len(p["changes"])} supported change{"s" if len(p["changes"]) != 1 else ""} since the previous observation; earlier evidence is retained.', 'claim_ids': sorted({i for ch in p['changes'] for i in ch.get('current_claim_ids', [])})})
    unknowns = [k for k, v in p['availability'].items() if v['state'] != 'available']
    if unknowns:
        narrative.append({'text': 'Not established from permitted exact-entity sources: ' + ', '.join(u.replace('_', ' ') for u in unknowns) + '. This is not proof of absence.', 'claim_ids': []})
    p['summary'] = {'title': name, 'narrative': narrative, 'facts': facts, 'unknowns': unknowns, 'changes_observed': len(p['changes']), 'method': 'Deterministic template over supported, undisputed claims; each sentence cites its claim ids; no model used'}
