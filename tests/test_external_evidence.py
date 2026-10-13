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
    assert [c['value'] for c in p['claims']] == ['https://example.com/contact']
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
