"""Integrity validation for actual research artifacts; never emits qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from .extract import pointer, html_document, site_root
from .models import Profile
from .runner import file_hash, read_inputs, read_jsonl, write_json


def audit(directory, universe_path=None):
    root=Path(directory).resolve()
    profiles=read_jsonl(root/'profiles.jsonl')
    envelopes=read_jsonl(root/'envelopes.jsonl')
    orgs=read_inputs(root/'entry-companies.jsonl')
    failures=[]; checked=0; locators=0; financial_values=0; html_locators=0
    if [p['organisation_number'] for p in profiles]!=orgs: failures.append('Profile association/order mismatch')
    if [e['organisation_number'] for e in envelopes]!=orgs: failures.append('Envelope association/order mismatch')
    if len(orgs)!=len(set(orgs)): failures.append('Duplicate inputs')
    allowed=None
    if universe_path:
        import gzip
        path=Path(universe_path)
        opener=gzip.open if path.suffix=='.gz' else open
        with opener(path,'rt',encoding='utf-8') as stream:
            allowed={json.loads(line)['organisation_number'] for line in stream if line.strip()}
        if not set(orgs)<=allowed: failures.append('Inputs outside eligible universe')
    cache={}
    for p,envelope in zip(profiles,envelopes):
        try: Profile.model_validate(p)
        except ValueError as exc: failures.append(str(exc)[:250]);continue
        if envelope['claims']!=p['claims'] or envelope['evidence']!=p['evidence']:
            failures.append(p['organisation_number']+': envelope/profile claims differ')
        evidence={e['id']:e for e in p['evidence']}
        snapshots={s['id']:s for s in p['source_snapshots']}
        for s in snapshots.values():
            if not s.get('path'): continue
            path=(root/s['path']).resolve()
            if not path.is_relative_to(root/'evidence'):
                failures.append('Unsafe snapshot path');continue
            if not path.exists(): failures.append('Missing evidence: '+s['path']);continue
            if str(path) not in cache:
                raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
                try: body=json.loads(raw)
                except (ValueError,UnicodeError): body=None
                cache[str(path)]=(sha,body,raw)
                checked+=1
            if cache[str(path)][0]!=s['retained_sha256']:
                failures.append('Retained evidence hash mismatch')
        for c in p['claims']:
            for eid in c['evidence_ids']:
                e=evidence[eid]
                datetime.fromisoformat(e['retrieved_at'].replace('Z','+00:00'))
                path=(root/(e.get('snapshot_path') or '')).resolve()
                entry=cache.get(str(path));body=entry[1] if entry else None
                if not entry:
                    failures.append('Claim evidence snapshot is missing')
                    continue
                if e['locator'].startswith('/') or e['locator']=='':
                    extracted=pointer(body,e['locator'])
                    if extracted is None: failures.append(f"{p['organisation_number']}: locator missing {e['locator']}")
                    else: locators+=1
                    if c['family']=='financials':
                        financial_values+=1
                        if extracted!=c['value']: failures.append('Financial value does not match source pointer')
                        if not c['period'] or not c['currency'] or not c['original_unit']: failures.append('Missing financial period/unit/currency')
                else:
                    doc=html_document(entry[2],e['source_url'])
                    locator=e['locator']; valid=False
                    if locator.startswith('text:'):
                        try:
                            _,start,end=locator.split(':');start,end=int(start),int(end)
                            span=doc['text'][start:end]
                            import re
                            exact_number=re.sub(r'\D','',span)==p['organisation_number']
                            exact_name=bool(p.get('name')) and re.sub(r'\s+',' ',span).rstrip('.').casefold()==re.sub(r'\s+',' ',p['name']).strip().casefold()
                            valid=0<=start<end<=len(doc['text']) and (exact_number or exact_name) and c['value'] in (e['source_url'],site_root(e['source_url']))
                        except (ValueError,TypeError): pass
                    elif locator.startswith('host:'):
                        from .extract import domain_matches_name
                        from urllib.parse import urlsplit
                        host=locator[len('host:'):]
                        valid=urlsplit(e['source_url']).hostname==host and c['value'] in (e['source_url'],site_root(e['source_url'])) and domain_matches_name(host,p.get('name'))
                    elif locator.startswith('link:'):
                        from .extract import social_profile
                        try: link=doc['links'][int(locator[len('link:'):])]
                        except (ValueError,IndexError): link=None
                        valid=bool(link) and isinstance(c['value'],dict) and link['url']==c['value'].get('href') and social_profile(link['url'])=={k:c['value'][k] for k in ('platform','url')}
                    elif locator=='css:meta[name="description"]@content':
                        valid=doc['description'] is not None and doc['description']==c['value']
                    elif locator=='css:meta[property="og:site_name"]@content':
                        valid=doc.get('site_name') is not None and doc['site_name']==c['value']
                    elif locator.startswith('jsonld:/'):
                        node=pointer(doc['structured'],locator[len('jsonld:'):])
                        if isinstance(node,str):
                            valid=isinstance(c['value'],dict) and node==c['value'].get('href')
                        else:
                            valid=isinstance(node,dict) and isinstance(c['value'],dict) and all(node.get(k)==v for k,v in c['value'].items())
                    if valid: html_locators+=1
                    else: failures.append(f"{p['organisation_number']}: HTML locator or value mismatch {locator}")
            if c['availability']=='available' and c['value'] is None: failures.append('Null marked available')
        for c in p['changes']:
            if not set(c['previous_evidence_ids']+c['current_evidence_ids'])<=set(evidence): failures.append('Unresolved change evidence')
    return {'passed':not failures,'profiles':len(profiles),'terminal_envelopes':len(envelopes),'unique_inputs':len(set(orgs)),'eligible_membership_verified':allowed is not None,'retained_snapshots_hash_checked':checked,'json_locators_resolved':locators,'html_locators_resolved':html_locators,'financial_values_matched_to_source':financial_values,'failures':failures,'independent_factual_accuracy':'not_measured','official_qualification':'not_determined'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--universe');p.add_argument('--report')
    args=p.parse_args();result=audit(args.directory,args.universe)
    if args.report:write_json(args.report,result)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__': main()
