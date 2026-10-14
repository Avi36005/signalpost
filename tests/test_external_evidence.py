import json

from aviscope.audit import audit
from aviscope.extract import external_extract, html_document, identity_gate
from aviscope.fetch import Broker, Budget
from aviscope.models import Profile
from aviscope.pipeline import enrich, envelope, finish
from aviscope.runner import write_jsonl

ORG = '945811714'


def make_profile():
    p = Profile(organisation_number=ORG, name='AMBITA AS').model_dump(mode='json')
    p['candidate_ledger'] = [{'url': 'https://example.com/', 'status': 'not_attempted'}]
    return p


def broker_for(tmp_path, pages):
    def transport(url, *args):
        if url.endswith('/robots.txt'):
            return 404, {}, b''
        return 200, {'Content-Type': 'text/html'}, pages[url].encode()
    broker = Broker(tmp_path, Budget(max_requests=20), transport=transport)
    broker._throttle = lambda *args: None
    return broker


def test_contact_identity_is_scoped_to_verified_page(tmp_path):
    pages = {'https://example.com/': '<meta name="description" content="Unsupported home claim"><a href="/contact">Contact</a>',
             'https://example.com/contact': '<p>AMBITA AS 945 811 714</p>'}
    p = enrich(make_profile(), broker_for(tmp_path, pages))
    assert p['availability']['website']['state'] == 'available'
    assert [c['value'] for c in p['claims']] == ['https://example.com/']
    assert p['candidate_ledger'][0]['verified_url'].endswith('/contact')


def test_shared_home_does_not_authorize_contact_probe(tmp_path):
    pages = {'https://example.com/': '<p>AMBITA AS 945811714 Parent 917886113</p><a href="/contact">Contact</a>'}
    broker = broker_for(tmp_path, pages)
    p = enrich(make_profile(), broker)
    assert not p['claims'] and p['availability']['website']['state'] == 'ambiguous'
    assert broker.budget.requests == 2


def test_html_audit_checks_exact_job_and_detects_tampering(tmp_path):
    jobs = [{'@type': 'JobPosting', 'title': title, 'datePosted': '2026-09-14',
             'hiringOrganization': {'taxID': ORG}} for title in ('Engineer', 'Designer')]
    raw = '<p>AMBITA AS 945811714</p><meta name="description" content="Company description"><script type="application/ld+json">' + json.dumps({'@graph': jobs}) + '</script>'
    broker = broker_for(tmp_path, {'https://example.com/': raw})
    p = finish(enrich(make_profile(), broker))
    job_claims = [c for c in p['claims'] if c['family'] == 'jobs']
    assert len(job_claims) == 2 and job_claims[0]['evidence_ids'] != job_claims[1]['evidence_ids']
    def save():
        write_jsonl(tmp_path/'profiles.jsonl', [p])
        write_jsonl(tmp_path/'envelopes.jsonl', [envelope(p, 'test', p['researched_at'])])
        write_jsonl(tmp_path/'entry-companies.jsonl', [{'organisation_number': ORG}])
    save()
    result = audit(tmp_path)
    assert result['passed'] and result['html_locators_resolved'] == 4
    job_claims[0]['value']['title'] = 'Invented title'
    save()
    assert not audit(tmp_path)['passed']


def test_followup_pages_do_not_conflict_with_website(tmp_path):
    raw = '<p>AMBITA AS 945811714</p>'
    broker = broker_for(tmp_path, {'https://example.com/': raw, 'https://example.com/contact': raw})
    p = make_profile()
    for url in ('https://example.com/', 'https://example.com/contact'):
        snapshot, content = broker.fetch(url, 'company_owned')
        p['source_snapshots'].append(snapshot)
        doc = html_document(content, url)
        external_extract(p, doc, snapshot, identity_gate(ORG, p['name'], doc, registry_linked=True))
    p = finish(p)
    assert p['availability']['website']['state'] == 'available'
    assert len(p['claims']) == 1 and not p['review_queue']


def test_verified_site_profiles_brand_jobs_articles_are_audited(tmp_path):
    org_jsonld = {'@type': 'Organization', 'name': 'Ambita', 'sameAs': ['https://www.instagram.com/ambita/', 'https://www.facebook.com/sharer.php?u=x']}
    job = {'@type': 'JobPosting', 'title': 'Utvikler', 'datePosted': '2026-10-01', 'hiringOrganization': {'@type': 'Organization', 'name': 'Ambita'}}
    foreign_job = {'@type': 'JobPosting', 'title': 'Kokk', 'datePosted': '2026-10-02', 'hiringOrganization': {'name': 'Other Company AS', 'taxID': '917886113'}}
    article = {'@type': 'NewsArticle', 'headline': 'Ny tjeneste', 'datePublished': '2026-09-30'}
    home = ('<meta property="og:site_name" content="Ambita"><p>AMBITA AS org.nr 945 811 714</p>'
            '<a href="https://www.facebook.com/ambita.no/">Facebook</a><a href="https://www.facebook.com/sharer/sharer.php?u=x">Del</a>'
            '<a href="https://no.linkedin.com/company/ambita-as">LinkedIn</a><a href="/karriere">Karriere</a><a href="/nyheter">Nyheter</a>'
            '<script type="application/ld+json">' + json.dumps(org_jsonld) + '</script>')
    careers = '<h1>Jobb hos oss</h1><script type="application/ld+json">' + json.dumps({'@graph': [job, foreign_job]}) + '</script>'
    news = '<h1>Nyheter</h1><script type="application/ld+json">' + json.dumps(article) + '</script>'
    pages = {'https://example.com/': home, 'https://example.com/karriere': careers, 'https://example.com/nyheter': news}
    p = finish(enrich(make_profile(), broker_for(tmp_path, pages)))
    fields = sorted((c['field'], json.dumps(c['value'], sort_keys=True)) for c in p['claims'])
    profiles = sorted(c['value']['url'] for c in p['claims'] if c['field'] == 'linked_profile')
    assert profiles == ['https://facebook.com/ambita.no', 'https://instagram.com/ambita', 'https://www.linkedin.com/company/ambita-as']
    assert [c['value']['title'] for c in p['claims'] if c['field'] == 'job_posting'] == ['Utvikler']
    assert [c['value']['headline'] for c in p['claims'] if c['field'] == 'company_article'] == ['Ny tjeneste']
    assert [c['value'] for c in p['claims'] if c['field'] == 'public_brand_name'] == ['Ambita']
    assert all(p['availability'][f]['state'] == 'available' for f in ('website', 'brand', 'company_profiles', 'jobs', 'public_activity')), fields
    write_jsonl(tmp_path/'profiles.jsonl', [p])
    write_jsonl(tmp_path/'envelopes.jsonl', [envelope(p, 'test', p['researched_at'])])
    write_jsonl(tmp_path/'entry-companies.jsonl', [{'organisation_number': ORG}])
    result = audit(tmp_path)
    assert result['passed'], result['failures']
    p['claims'][[c['field'] for c in p['claims']].index('linked_profile')]['value']['url'] = 'https://facebook.com/someone-else'
    write_jsonl(tmp_path/'profiles.jsonl', [p])
    write_jsonl(tmp_path/'envelopes.jsonl', [envelope(p, 'test', p['researched_at'])])
    assert not audit(tmp_path)['passed']


def test_registry_domain_spelling_name_is_audited(tmp_path):
    pages = {'https://www.ambita.no/': '<h1>Velkommen</h1>'}
    p = make_profile(); p['candidate_ledger'] = [{'url': 'www.ambita.no', 'source': 'official_registry', 'status': 'not_attempted'}]
    p = finish(enrich(p, broker_for(tmp_path, {'https://www.ambita.no/': pages['https://www.ambita.no/']})))
    website = [c for c in p['claims'] if c['field'] == 'official_website']
    assert [c['value'] for c in website] == ['https://www.ambita.no/']
    assert p['evidence'][0]['locator'] == 'host:www.ambita.no'
    write_jsonl(tmp_path/'profiles.jsonl', [p])
    write_jsonl(tmp_path/'envelopes.jsonl', [envelope(p, 'test', p['researched_at'])])
    write_jsonl(tmp_path/'entry-companies.jsonl', [{'organisation_number': ORG}])
    assert audit(tmp_path)['passed']


def test_robots_unauthorized_means_no_restrictions_but_server_error_blocks(tmp_path):
    def transport(url, *args):
        if url == 'https://open.example/robots.txt': return 401, {}, b''
        if url == 'https://down.example/robots.txt': return 503, {}, b''
        return 200, {'Content-Type': 'text/html'}, b'<p>ok</p>'
    broker = Broker(tmp_path, Budget(max_requests=20), transport=transport)
    broker._throttle = lambda *args: None
    assert broker.fetch('https://open.example/', 'company_owned')[0]['status'] == 200
    import pytest
    with pytest.raises(ValueError):
        broker.fetch('https://down.example/', 'company_owned')


def test_site_builder_and_personal_profiles_are_not_company_profiles(tmp_path):
    home = ('<p>AMBITA AS 945811714</p><a href="https://www.facebook.com/wix">Wix</a><a href="https://twitter.com/wix">Wix</a>'
            '<a href="https://www.facebook.com/olga.kristoffersen">Olga</a><a href="https://www.instagram.com/ambita_no/">Instagram</a>')
    p = finish(enrich(make_profile(), broker_for(tmp_path, {'https://example.com/': home})))
    assert [c['value']['url'] for c in p['claims'] if c['field'] == 'linked_profile'] == ['https://instagram.com/ambita_no']


def test_one_company_description_per_profile(tmp_path):
    home = '<meta name="description" content="Home"><p>AMBITA AS 945811714</p><a href="/kontakt">Kontakt</a>'
    contact = '<meta name="description" content="Contact page"><p>AMBITA AS 945811714</p>'
    p = finish(enrich(make_profile(), broker_for(tmp_path, {'https://example.com/': home, 'https://example.com/kontakt': contact})))
    assert [c['value'] for c in p['claims'] if c['field'] == 'company_description'] == ['Home']
    assert p['availability']['brand']['state'] == 'available' and not p['review_queue']


def test_narrative_sentences_cite_existing_claims(tmp_path):
    home = '<meta name="description" content="Eiendomsdata for Norge"><p>AMBITA AS 945811714</p>'
    p = finish(enrich(make_profile(), broker_for(tmp_path, {'https://example.com/': home})))
    ids = {c['id'] for c in p['claims']}
    narrative = p['summary']['narrative']
    assert any('Eiendomsdata for Norge' in x['text'] for x in narrative)
    assert all(set(x['claim_ids']) <= ids for x in narrative)
    assert narrative[-1]['text'].startswith('Not established') and 'jobs' in narrative[-1]['text']
    assert not any('revenue' in x['text'] for x in narrative)
    assert envelope(p, 'test', p['researched_at'])['summary'] == p['summary']


def test_registry_section_url_is_kept_and_generic_text_is_not_a_name(tmp_path):
    p = make_profile(); p['candidate_ledger'] = [{'url': 'example.com/ambita', 'source': 'official_registry', 'status': 'not_attempted'}]
    p = finish(enrich(p, broker_for(tmp_path, {'https://example.com/ambita': '<p>Ambita AS, org nr 945 811 714</p>'})))
    assert [c['value'] for c in p['claims'] if c['field'] == 'official_website'] == ['https://example.com/ambita']
    assert not identity_gate(ORG, 'AMBITA AS', {'text': 'you can ambita as needed'}, registry_linked=True)['publishable']
    assert not identity_gate(ORG, 'AMBITA AS', {'text': 'Ambita AB Stockholm. Ambita AS Oslo'}, registry_linked=True)['publishable']


def test_one_profile_per_platform_prefers_company_handle(tmp_path):
    home = ('<p>AMBITA AS 945811714</p><a href="https://www.facebook.com/vibekeambita">V</a>'
            '<a href="https://www.facebook.com/Ambita">A</a><a href="https://www.instagram.com/ambita.no">I</a>')
    p = finish(enrich(make_profile(), broker_for(tmp_path, {'https://example.com/': home})))
    assert sorted(c['value']['url'] for c in p['claims'] if c['field'] == 'linked_profile') == ['https://facebook.com/Ambita', 'https://instagram.com/ambita.no']
