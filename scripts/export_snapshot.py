"""Export a sanitised, read-only AviScope research snapshot for the public website.

Input: terminal envelopes (``envelopes.jsonl`` or ``.jsonl.gz``, schema ``aviscope-1``) plus the run report.
Envelopes are not profiles: the legal name lives at ``legal_identity.name`` (profiles use ``name``) and
workbench-only fields (candidate ledger, identity links, review queue) are absent. This adapter reads
envelopes explicitly and never treats the two formats as interchangeable.

Output (``--out``):
  manifest.json            dataset label, run id, source commit, retrieval window, counts, exclusions
  index.json               one small search row per company (name, number, place, industry, latest revenue)
  companies/<orgnr>.json   cited summary, claims, evidence receipts, availability, changes, revenue comparison

Excluded on purpose: local snapshot paths, retained raw page bodies, request journals, fetch logs, error
traces, operations timings, credentials. Evidence excerpts are capped at 240 characters.
The current identity rule is re-applied: a website-family claim whose only identity evidence is a
host-name match (``host:`` locator) is withheld, because it lacks on-page proof of the exact company.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aviscope.extract import revenue_comparison, revenue_sentence  # noqa: E402
from aviscope.models import org_number  # noqa: E402

EXPORT_SCHEMA = 'aviscope-site-snapshot-1'
EXCERPT_LIMIT = 240
WEB_FAMILIES = {'website', 'company_profiles', 'brand'}
EVIDENCE_KEYS = ('id', 'source_url', 'source_class', 'retrieved_at', 'locator', 'identity_basis', 'retention', 'content_sha256', 'extraction_method')
CLAIM_KEYS = ('id', 'field', 'family', 'value', 'availability', 'evidence_ids', 'period', 'effective_at', 'currency', 'original_unit', 'scope', 'derived_from', 'stale', 'first_observed_at', 'last_observed_at')


def read_envelopes(path: Path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if row.get('schema_version') != 'aviscope-1':
                    raise ValueError(f"Unsupported envelope schema: {row.get('schema_version')!r}")
                if 'legal_identity' not in row or 'name' in row:
                    raise ValueError('Input looks like a profile, not a terminal envelope; use an envelopes file')
                yield row


def _excerpt(value):
    if not value: return None
    value = ' '.join(str(value).split())
    return value if len(value) <= EXCERPT_LIMIT else value[:EXCERPT_LIMIT - 1] + '…'


def _safe_url(url):
    return url if isinstance(url, str) and url.startswith(('https://', 'http://')) else None


def _first(claims, field):
    return next((c for c in claims if c['field'] == field and c['availability'] == 'available' and not c['stale']), None)


def company_detail(env):
    org = org_number(env['organisation_number'])
    evidence = {e['id']: e for e in env['evidence']}
    withheld = []
    claims = []
    for c in env['claims']:
        if c['family'] in WEB_FAMILIES:
            locators = [evidence[i].get('locator') or '' for i in c['evidence_ids'] if i in evidence]
            if locators and all(l.startswith('host:') for l in locators):
                withheld.append({'field': c['field'], 'reason': 'Host-name match only; no on-page proof of the exact company'})
                continue
        claims.append({k: c.get(k) for k in CLAIM_KEYS})
    kept_claim_ids = {c['id'] for c in claims}
    used = {i for c in claims for i in c['evidence_ids']}
    receipts = []
    for i in sorted(used):
        e = evidence.get(i)
        if not e: continue
        r = {k: e.get(k) for k in EVIDENCE_KEYS}
        r['source_url'] = _safe_url(r['source_url'])
        r['excerpt'] = _excerpt(e.get('excerpt'))
        receipts.append(r)
    narrative = []
    for item in env['summary'].get('narrative', []):
        ids = [i for i in item.get('claim_ids', []) if i in kept_claim_ids]
        if item.get('claim_ids') and not ids: continue
        narrative.append({'text': item['text'], 'claim_ids': ids})
    comparison = revenue_comparison(claims)
    revenue_history = sorted(
        ({'year': (c['period'] or {}).get('tilDato', '')[:4], 'period': c['period'], 'value': c['value'], 'currency': c['currency'], 'original_unit': c['original_unit'], 'claim_id': c['id']}
         for c in claims if c['field'] == 'revenue' and c['scope'] == 'legal_entity' and c['availability'] == 'available' and isinstance(c['value'], (int, float)) and c.get('period')),
        key=lambda r: r['period'].get('tilDato', ''))
    return {
        'schema_version': EXPORT_SCHEMA,
        'organisation_number': org,
        'legal_name': env['legal_identity'].get('name'),
        'run': env['run'],
        'summary': {
            'title': env['summary'].get('title'),
            'narrative': narrative,
            'unknowns': env['summary'].get('unknowns', []),
            'revenue_comparison': comparison,
            'revenue_comparison_text': revenue_sentence(comparison) if comparison else None,
        },
        'revenue_history': revenue_history,
        'claims': claims,
        'evidence': receipts,
        'availability': {k: {'state': v.get('state'), 'reason': v.get('reason')} for k, v in env['availability'].items()},
        'changes': env.get('changes', []),
        'refresh': env.get('refresh'),
        'withheld_by_current_identity_rule': withheld,
    }


def index_row(detail):
    claims = detail['claims']
    def value(field):
        c = _first(claims, field); return c['value'] if c else None
    address = value('head_office_address') or value('registered_address') or {}
    latest = detail['revenue_history'][-1] if detail['revenue_history'] else None
    website = _first(claims, 'official_website')
    return {
        'organisation_number': detail['organisation_number'],
        'legal_name': detail['legal_name'],
        'legal_form': value('legal_form'),
        'municipality': address.get('kommune') if isinstance(address, dict) else None,
        'postal_place': address.get('poststed') if isinstance(address, dict) else None,
        'industry': value('industry'),
        'employees': value('employees'),
        'latest_revenue': {'value': latest['value'], 'currency': latest['currency'], 'year': latest['year']} if latest else None,
        'revenue_change_percent': (detail['summary']['revenue_comparison'] or {}).get('percent_change'),
        'website': website['value'] if website else None,
        'families_available': sum(v['state'] == 'available' for v in detail['availability'].values()),
        'claim_count': len(claims),
        'checked_at': (detail['refresh'] or {}).get('checked_at') or detail['run'].get('completed_at'),
    }


def export(envelopes_path: Path, report_path: Path | None, out: Path, label: str):
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path else {}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'companies').mkdir(exist_ok=True)
    index, seen = [], set()
    for env in read_envelopes(envelopes_path):
        detail = company_detail(env)
        if detail['organisation_number'] in seen:
            raise ValueError('Duplicate organisation number in envelopes')
        seen.add(detail['organisation_number'])
        (out / 'companies' / f"{detail['organisation_number']}.json").write_text(json.dumps(detail, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        index.append(index_row(detail))
    index_bytes = json.dumps(index, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    (out / 'index.json').write_bytes(index_bytes)
    retrieved = sorted(r['checked_at'] for r in index if r['checked_at'])
    manifest = {
        'schema_version': EXPORT_SCHEMA,
        'label': label,
        'mode': 'research_snapshot',
        'description': 'A labelled sample of real AviScope research output. It is not live data and does not cover all Norwegian companies.',
        'company_count': len(index),
        'run_id': report.get('run_id'),
        'source_commit': report.get('source_commit'),
        'source_repository': 'https://github.com/Avi36005/signalpost',
        'input_sha256': report.get('input_sha256'),
        'retrieved_from': retrieved[0] if retrieved else None,
        'retrieved_to': retrieved[-1] if retrieved else None,
        'exported_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'envelopes_sha256': hashlib.sha256(envelopes_path.read_bytes()).hexdigest(),
        'index_sha256': hashlib.sha256(index_bytes).hexdigest(),
        'files': {'index': 'index.json', 'company': 'companies/{organisation_number}.json'},
        'excluded': ['local snapshot paths', 'retained raw page bodies', 'request journals and fetch logs', 'error traces and timings', 'credentials'],
        'identity_rule': 'Website, brand and profile claims are shown only with on-page proof of the exact legal name or organisation number.',
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--envelopes', required=True)
    p.add_argument('--report')
    p.add_argument('--out', required=True)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    m = export(Path(a.envelopes), Path(a.report) if a.report else None, Path(a.out), a.label)
    print(json.dumps({k: m[k] for k in ('label', 'company_count', 'run_id', 'source_commit', 'retrieved_from', 'retrieved_to')}, indent=2))


if __name__ == '__main__':
    main()
