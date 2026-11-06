"""The public-site snapshot adapter reads terminal envelopes (not profiles), re-applies the current
identity rule and never leaks local paths, retained bodies or error traces."""
import gzip
import json
from pathlib import Path

import pytest

from scripts.export_snapshot import company_detail, export, read_envelopes

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / 'docs' / 'smoke-test' / 'smoke-100-envelopes.jsonl.gz'
REPORT = ROOT / 'docs' / 'smoke-test' / 'smoke-100-run-report.json'


def envelope(**overrides):
    ev = lambda i, locator, url='https://example.no/': {'id': i, 'source_url': url, 'source_class': 'company_website', 'retrieved_at': '2026-10-14T11:11:01Z',
                                                        'locator': locator, 'excerpt': 'x' * 500, 'identity_basis': 'exact', 'snapshot_path': 'C:/private/snap.html',
                                                        'content_sha256': 'a' * 64, 'retention': 'hash_only', 'extraction_method': 'html'}
    claim = lambda i, field, family, value, eids, **kw: {'id': i, 'field': field, 'family': family, 'value': value, 'availability': 'available', 'evidence_ids': eids,
                                                          'period': kw.get('period'), 'currency': kw.get('currency'), 'original_unit': kw.get('original_unit'),
                                                          'scope': 'legal_entity', 'stale': False}
    env = {
        'schema_version': 'aviscope-1', 'organisation_number': '923609016',
        'legal_identity': {'name': 'EKSEMPEL AS'},
        'run': {'run_id': 'r1', 'completed_at': '2026-10-14T11:12:00Z'},
        'summary': {'title': 'EKSEMPEL AS', 'narrative': [{'text': 'Site: example.no', 'claim_ids': ['c-web']}, {'text': 'Registered.', 'claim_ids': ['c-name']}], 'unknowns': []},
        'claims': [claim('c-name', 'legal_name', 'legal_identity', 'EKSEMPEL AS', ['e-reg']),
                   claim('c-web', 'official_website', 'website', 'https://example.no/', ['e-host']),
                   claim('c-r24', 'revenue', 'financials', 100.0, ['e-reg'], period={'fraDato': '2024-01-01', 'tilDato': '2024-12-31'}, currency='NOK', original_unit='u'),
                   claim('c-r25', 'revenue', 'financials', 150.0, ['e-reg'], period={'fraDato': '2025-01-01', 'tilDato': '2025-12-31'}, currency='NOK', original_unit='u')],
        'evidence': [ev('e-reg', 'json:/navn', 'https://data.brreg.no/enhetsregisteret/api/enheter/923609016'), ev('e-host', 'host:example.no')],
        'availability': {'website': {'state': 'available', 'reason': None, 'debug': 'trace'}},
        'errors': [{'reason': 'Traceback (most recent call last): C:/Users/private'}],
    }
    env.update(overrides)
    return env


def test_host_only_website_claims_are_withheld_and_their_narrative_dropped():
    d = company_detail(envelope())
    assert 'official_website' not in {c['field'] for c in d['claims']}
    assert d['withheld_by_current_identity_rule'][0]['field'] == 'official_website'
    assert [n['text'] for n in d['summary']['narrative']] == ['Registered.']
    assert {e['id'] for e in d['evidence']} == {'e-reg'}


def test_private_fields_are_not_exported_and_excerpts_are_capped():
    blob = json.dumps(company_detail(envelope()))
    assert 'snapshot_path' not in blob and 'C:/private' not in blob and 'Traceback' not in blob and 'debug' not in blob
    assert all(len(e['excerpt']) <= 240 for e in company_detail(envelope())['evidence'])


def test_revenue_comparison_is_derived_from_cited_claims():
    s = company_detail(envelope())['summary']
    assert s['revenue_comparison']['status'] == 'compared' and s['revenue_comparison']['percent_change'] == 50.0
    assert '2025' in s['revenue_comparison_text'] and '2024' in s['revenue_comparison_text']


def test_profiles_are_rejected_as_input(tmp_path):
    path = tmp_path / 'profiles.jsonl'
    path.write_text(json.dumps({'schema_version': 'aviscope-1', 'organisation_number': '923609016', 'name': 'X'}) + '\n')
    with pytest.raises(ValueError, match='profile'):
        list(read_envelopes(path))


def test_duplicate_organisations_are_rejected(tmp_path):
    path = tmp_path / 'envelopes.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        f.write(json.dumps(envelope()) + '\n' + json.dumps(envelope()) + '\n')
    with pytest.raises(ValueError, match='Duplicate'):
        export(path, None, tmp_path / 'out', 'test')


@pytest.mark.skipif(not SMOKE.exists(), reason='published smoke envelopes not present')
def test_published_smoke_run_exports_one_file_per_company(tmp_path):
    manifest = export(SMOKE, REPORT, tmp_path / 'site', 'test label')
    index = json.loads((tmp_path / 'site' / 'index.json').read_text(encoding='utf-8'))
    assert manifest['company_count'] == len(index) == 100 == len(list((tmp_path / 'site' / 'companies').glob('*.json')))
    assert manifest['source_commit'] == json.loads(REPORT.read_text(encoding='utf-8'))['source_commit']
    blob = '\n'.join(p.read_text(encoding='utf-8') for p in (tmp_path / 'site' / 'companies').glob('*.json'))
    assert 'snapshot_path' not in blob and '\\Users\\' not in blob and '/Users/' not in blob
