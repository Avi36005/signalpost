"""Freeze/export, package, extract and audit the actual entry. Never sends or uploads."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aviscope.audit import audit
from aviscope.runner import code_hash,file_hash,read_jsonl,write_json,write_jsonl

# Token prefixes must start a token: retained page text such as 'nordisk-eik-...' is not a key.
SECRET=re.compile(rb'(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{30,}|(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{40,}|(?<![A-Za-z0-9-])sk-[A-Za-z0-9_-]{35,})')


WEBSITE_URL='https://build-the-actual-working-website-now-do.sites.jboxai.com/'
SITE_DATASET='docs/site-snapshot/2026-10-smoke-100 (run aviscope-20261014T110930Z, exported at commit 0ca4301b45b03f10d4d30d965808fe9f7ebc7c27)'


def safe_extract(archive,destination):
    root=Path(destination).resolve();root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist())>10_000_000_000:raise ValueError('Archive expands beyond 10 GB')
        for info in z.infolist():
            path=PurePosixPath(info.filename)
            target=(root/info.filename).resolve()
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename or not target.is_relative_to(root) or (info.external_attr>>16)&0o170000==0o120000:
                raise ValueError('Unsafe ZIP path or link')
        z.extractall(root)


def verify(archive,clean_smoke=False):
    archive=Path(archive).resolve()
    directory=Path(tempfile.mkdtemp(prefix='aviscope-verify-',dir=ROOT/'dist'))
    safe_extract(archive,directory)
    base=directory/'aviscope-signalpost-submission'
    expected={}
    for line in (base/'SHA256SUMS.txt').read_text().splitlines():
        sha,relative=line.split('  ',1)
        target=(base/relative).resolve()
        if not target.is_relative_to(base):raise ValueError('Checksum path escapes package')
        if file_hash(target)!=sha:raise ValueError('Checksum mismatch: '+relative)
        expected[relative]=sha
    payload={p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file() and p.name!='SHA256SUMS.txt'}
    if payload!=set(expected):raise ValueError('Payload/checksum membership mismatch')
    parsed=0
    for path in base.rglob('*'):
        if path.suffix=='.json':json.loads(path.read_text(encoding='utf-8-sig'));parsed+=1
        elif path.suffix=='.jsonl':read_jsonl(path);parsed+=1
        if path.is_file() and SECRET.search(path.read_bytes()):raise ValueError('Potential credential pattern in '+str(path.relative_to(base)))
    integrity=audit(base/'data')
    if not integrity['passed']:raise ValueError(str(integrity['failures'][:10]))
    manifest=json.loads((base/'submission-manifest.json').read_text())
    source_version=(base/'source/SOURCE_VERSION').read_text().strip()
    if source_version!=manifest['source_commit']:raise ValueError('Source version mismatch')
    for key,filename in [('profile_count','profiles.jsonl'),('envelope_count','envelopes.jsonl'),('unique_input_count','entry-companies.jsonl')]:
        if manifest[key]!=len(read_jsonl(base/'data'/filename)):raise ValueError('Manifest count mismatch')
    clean_result={'performed':False}
    if clean_smoke:
        source=base/'source'
        install=subprocess.run(['uv','sync','--frozen'],cwd=source,capture_output=True,text=True)
        if install.returncode:raise ValueError('Extracted locked install failed: '+install.stderr[-1000:])
        orgs=read_jsonl(base/'data/entry-companies.jsonl')[:2]
        write_jsonl(source/'smoke-input.jsonl',orgs)
        command=['uv','run','--frozen','python','-m','aviscope.runner','--organisations','smoke-input.jsonl','--expected-count',str(len(orgs)),'--output-dir','out/package-smoke','--max-requests','0']
        executed=subprocess.run(command,cwd=source,capture_output=True,text=True)
        if executed.returncode:raise ValueError('Extracted runner failed: '+executed.stderr[-1000:])
        result=json.loads((source/'out/package-smoke/run-report.json').read_text())
        if result['terminal_count']!=len(orgs) or result['operations']['requests']!=0:raise ValueError('Extracted smoke invalid')
        clean_result={'performed':True,'locked_install':True,'command':command,'terminal_count':result['terminal_count'],'outbound_requests':0,'research_quality':'not tested by offline smoke'}
    return {'passed':True,'zip_sha256':file_hash(archive),'payload_files_verified':len(expected),'json_files_parsed':parsed,'artifact_integrity':integrity,'clean_setup_smoke':clean_result,'extracted_directory':str(base)}


def package(data_dir,live_report,extra_reports=None):
    data=Path(data_dir).resolve();live=Path(live_report)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
    if dirty:raise ValueError('Commit tracked source changes before packaging')
    report=json.loads((data/'run-report.json').read_text())
    live_data=json.loads(live.read_text())
    if report['source_commit']!=sha or live_data['source_commit']!=sha:raise ValueError('Final corpus and live-100 must run on the exact frozen HEAD')
    if report['settings']['code_sha256']!=code_hash():raise ValueError('Runtime source differs from corpus')
    if live_data['source_code_sha256']!=code_hash() or live_data['input_count']!=100 or live_data['terminal_count']!=100:
        raise ValueError('Live report must measure exactly 100 inputs using frozen runtime source')
    if not all(live_data['budget_checks'].values()) or not all(live_data['validation'].values()):
        raise ValueError('Live batch failed resource or output checks')
    integrity=audit(data,ROOT/'downloads/universe.jsonl.gz')
    if not integrity['passed']:raise ValueError('Data integrity audit failed')
    now=datetime.now(timezone.utc);stem=f'AviScope_Avinash_Signalpost_{now:%Y%m%d}_{sha[:8]}'
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    build=Path(tempfile.mkdtemp(prefix='package-',dir=dist));base=build/'aviscope-signalpost-submission';base.mkdir()
    raw=subprocess.check_output(['git','archive','--format=zip',sha],cwd=ROOT)
    safe_extract(io.BytesIO(raw),base/'source')
    (base/'source/SOURCE_VERSION').write_text(sha+'\n')
    for d in ('data','reports','refresh','docs','email'): (base/d).mkdir()
    for filename in ('profiles.jsonl','envelopes.jsonl','entry-companies.jsonl','source-manifest.jsonl','review-queue.jsonl','changes.jsonl'):
        shutil.copyfile(data/filename,base/'data'/filename)
    referenced={s['path'] for p in read_jsonl(data/'profiles.jsonl') for s in p['source_snapshots'] if s.get('path')}
    for relative in referenced:
        source=(data/relative).resolve();target=(base/'data'/relative).resolve()
        if not source.is_relative_to(data/'evidence') or not target.is_relative_to(base/'data/evidence'):raise ValueError('Unsafe evidence path')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    shutil.copyfile(data/'run-report.json',base/'reports/submission-run-report.json')
    shutil.copyfile(live,base/'reports/live-100-report.json')
    write_json(base/'reports/integrity-report.json',integrity)
    for path in (ROOT/'reports').glob('*'):
        if path.is_file() and path.suffix in ('.json','.xml','.md'):shutil.copyfile(path,base/'reports'/path.name)
    evaluation=ROOT/'reports/evaluation'
    if evaluation.exists():
        for path in evaluation.iterdir():
            if path.is_file():shutil.copyfile(path,base/('refresh' if path.name in ('previous-snapshot.jsonl','current-snapshot.jsonl','changes.jsonl','refresh-report.json') else 'reports')/path.name)
    for path in (base/'source').glob('*.md'):shutil.copyfile(path,base/'docs'/path.name)
    for path in (base/'source/docs').glob('*.md'):shutil.copyfile(path,base/'docs'/path.name)
    if (ROOT/'docs/screenshots').exists():shutil.copytree(ROOT/'docs/screenshots',base/'docs/screenshots')
    for name in ('SUBMISSION_README.md','SUBMISSION_CHECKLIST.md'):shutil.copyfile(base/'source'/name,base/name)
    local_origin=subprocess.check_output(['git','remote','get-url','origin'],cwd=ROOT,text=True).strip()
    remote='https://github.com/Avi36005/signalpost'
    blockers=['Official coverage, precision and qualification are determined only by the organiser; local coverage counts are not recall against the checked pool.',
              'The cause of the organiser observation that 108 of 300 companies were reached is not established from local evidence; a clarification request is drafted (email/clarification-108-of-300.txt).',
              'Independent news search: no reliable licensed zero-cost provider is enabled (see docs/NOV2026_CHANGE_PLAN.md).',
              'NAV job-ad feed: production use requires consumer registration with NAV, which has not been done.',
              'Starter archive contains no explicit code licence; confirm redistribution terms.',
              'Results contact address must be confirmed by Avinash before any draft is sent.']
    # October 2026 contract: a 100-company smoke-test result is required; precomputed corpora are optional and unscored.
    manifest={'schema_version':'aviscope-submission-1','agent':'AviScope','entrant':'Avinash','created_at':now.isoformat(),'repository_url':remote,'source_commit':sha,'source_code_sha256':code_hash(),'dependency_lock_sha256':file_hash(ROOT/'uv.lock'),'universe_archive_sha256':'1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384','universe_content_sha256':'b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838','unique_input_count':report['input_count'],'profile_count':report['unique_profiles'],'researched_profile_count':report['researched_profiles'],'partial_profile_count':report['partial_profiles'],'failed_input_count':report['failed_inputs'],'envelope_count':report['terminal_count'],'dataset_sha256':{f:file_hash(base/'data'/f) for f in ('entry-companies.jsonl','profiles.jsonl','envelopes.jsonl','source-manifest.jsonl')},'evaluator_command':'uv sync --frozen && uv run python -m aviscope.runner --organisations BATCH_FILE --output-dir out/official --history --max-cost 0','required_secret_environment_variables':[],'models':'none; deterministic extraction and synthesis','enabled_api':'Brreg public official APIs','expected_cost_per_official_run_usd':0,'cost_basis':'No chargeable provider enabled; measured official-data runs declare zero API spend.','reviewer_access':'public GitHub repository','website_url':WEBSITE_URL,'website_provenance':'docs/JBOX_BUILD_PROVENANCE.md','website_dataset':SITE_DATASET,'readiness':{'implementation_complete':False,'local_validation_passed':integrity['passed'] and all(live_data['budget_checks'].values()),'submission_artifacts_complete':live_data['terminal_count']==live_data['input_count']==100,'reviewer_access_verified':True,'email_ready':False},'official_qualification':'not_determined','readiness_blockers':blockers,'refresh_scope':'Retained live submission corpus unchanged replay, not manufactured historical snapshots','evidence_directory':'data/evidence','email_sent':False}
    write_json(base/'submission-manifest.json',manifest)
    manifest['local_origin_url']=local_origin
    manifest['repository_url_status']='Public repository; branch pushed and served by jsDelivr at the pinned snapshot commit'
    manifest['enabled_sources']=['Brreg public official APIs','Registry-linked or name-spelled company websites subject to robots and on-page exact-entity checks','Social profiles linked from a verified company website (destinations not fetched)']
    write_json(base/'submission-manifest.json',manifest)
    checklist=(base/'SUBMISSION_CHECKLIST.md').read_text()+'\n## Generated measured status\n\n'+f"- Researched profiles: {report['researched_profiles']}; partial: {report['partial_profiles']}; failed: {report['failed_inputs']}.\n- Exact source: `{sha}`.\n- Live 100: {live_data['operations']['runtime_seconds']} seconds, {live_data['operations']['requests']} requests, $0 API spend.\n- Local data integrity: passed.\n- ZIP/extracted verification: see external package verification report; generated after archive construction.\n\n"+'\n'.join('- Pending: '+b for b in blockers)+'\n'
    (base/'SUBMISSION_CHECKLIST.md').write_text(checklist,encoding='utf-8')
    extras=[]
    for path in extra_reports or []:
        path=Path(path);extra=json.loads(path.read_text(encoding='utf-8'))
        if extra.get('source_commit')!=sha:raise ValueError('Extra report was not produced by HEAD: '+str(path))
        shutil.copyfile(path,base/'reports'/(path.parent.name+'-run-report.json'));extras.append(extra)
    # Email drafts are written by hand in docs/submission-drafts/ and never sent. {{name}} fields are filled only
    # from the reports above; a field without a measured value stops packaging instead of leaving a placeholder.
    values={'commit':sha,'short_commit':sha[:8],'zip_name':stem+'.zip','website_url':WEBSITE_URL}
    for prefix,run in [('smoke',live_data)]+[('extra'+(str(i) if i else ''),r) for i,r in enumerate(extras)]:
        ops=run['operations'];cov=run['field_coverage']
        values.update({f'{prefix}_input':run['input_count'],f'{prefix}_terminal':run['terminal_count'],f'{prefix}_failed':run['failed_inputs'],
                       f'{prefix}_runtime':round(ops['runtime_seconds']),f'{prefix}_requests':ops['requests'],f'{prefix}_cost':f"{ops['third_party_cost_usd']:.2f}",
                       f'{prefix}_run_id':run['run_id']}|{f'{prefix}_{k}':v for k,v in cov.items()})
    profiles=read_jsonl(data/'profiles.jsonl');comparisons=[(x.get('summary') or {}).get('revenue_comparison') for x in profiles]
    values['smoke_revenue_compared']=sum(1 for c in comparisons if c and c['status'] in ('compared','compared_without_percentage'))
    values['smoke_revenue_not_compared']=len(profiles)-values['smoke_revenue_compared']
    for state in ('available','ambiguous','blocked','not_available','failed'):
        values['smoke_website_'+state]=sum(1 for x in profiles if x['availability'].get('website',{}).get('state')==state)
    def fill(path,extra):
        text=re.sub(r'\{\{(\w+)\}\}',lambda m:str((values|extra)[m.group(1)]) if m.group(1) in values|extra else m.group(0),path.read_text(encoding='utf-8'))
        if re.search(r'\{\{\w+\}\}|<[A-Za-z][^<>@]*>',text):raise ValueError('Unfilled field in email draft '+path.name)
        return text
    drafts=sorted((ROOT/'docs/submission-drafts').glob('*.txt'))
    if not drafts:raise ValueError('No email drafts in docs/submission-drafts')
    for path in drafts:
        (base/'email'/path.name).write_text(fill(path,{'zip_sha256':'in the separate '+stem+'.zip.sha256 file'}),encoding='utf-8')
    payload=[p for p in base.rglob('*') if p.is_file()]
    for path in payload:
        if SECRET.search(path.read_bytes()):raise ValueError('Potential secret pattern: '+str(path.relative_to(base)))
    (base/'SHA256SUMS.txt').write_text(''.join(file_hash(p)+'  '+p.relative_to(base).as_posix()+'\n' for p in sorted(payload)),encoding='utf-8')
    archive=dist/(stem+'.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(base.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(build).as_posix())
    checksum=file_hash(archive);Path(str(archive)+'.sha256').write_text(checksum+'  '+archive.name+'\n')
    checked=verify(archive,clean_smoke=True)
    checked.update(zip_bytes=archive.stat().st_size,source_commit=sha,email_sent=False)
    write_json(dist/(stem+'-verification.json'),checked)
    # Copies outside the archive can quote the archive's own checksum.
    for path in drafts:(dist/(stem+'-'+path.name)).write_text(fill(path,{'zip_sha256':checksum}),encoding='utf-8')
    write_json(dist/'latest.json',{'zip':str(archive),'checksum':str(archive)+'.sha256','verification':str(dist/(stem+'-verification.json')),'manifest':str(base/'submission-manifest.json'),'submission_readme':str(base/'SUBMISSION_README.md'),'checklist':str(base/'SUBMISSION_CHECKLIST.md'),'email_drafts':[str(dist/(stem+'-'+p.name)) for p in drafts],'source_commit':sha})
    print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':checksum,'verified':checked['passed'],'readiness':manifest['readiness']},indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default='out/submission');p.add_argument('--live-report',default='out/live-100/run-report.json');p.add_argument('--verify');p.add_argument('--extra-report',action='append',help='Additional run report (for example a 300-company run) copied into reports/');args=p.parse_args()
    (ROOT/'dist').mkdir(exist_ok=True)
    if args.verify:print(json.dumps(verify(args.verify),indent=2))
    else:package(args.data_dir,args.live_report,args.extra_report)


if __name__=='__main__':main()
