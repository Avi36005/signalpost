"""Freeze/export, package, extract and audit the actual entry. Never sends or uploads."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import SMTP
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

SECRET=re.compile(rb'(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9_-]{35,})')


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


def package(data_dir,live_report):
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
    now=datetime.now(timezone.utc);stem=f'aviscope-avinash-signalpost-submission-{now:%Y%m%d}-{sha[:8]}'
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
    blockers=['Company-owned external research is enabled by default and verified live, but whether it yields sufficient coverage for the challenge gates (>=21/35, >=60% weighted external recall) at full-corpus scale is not yet established.','Independent human quality review and official coverage/precision gates are unverified.','Starter archive contains no explicit code licence; confirm redistribution terms.','Repository destination confirmation, authorized push and exact reviewer access are pending.','Accessible organisation-number manifest URL is pending authorized publication.','Verified contact for results is missing.']
    # October 2026 contract: a 100-company smoke-test result is required; precomputed corpora are optional and unscored.
    manifest={'schema_version':'aviscope-submission-1','agent':'AviScope','entrant':'Avinash','created_at':now.isoformat(),'repository_url':remote,'source_commit':sha,'source_code_sha256':code_hash(),'dependency_lock_sha256':file_hash(ROOT/'uv.lock'),'universe_archive_sha256':'1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384','universe_content_sha256':'b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838','unique_input_count':report['input_count'],'profile_count':report['unique_profiles'],'researched_profile_count':report['researched_profiles'],'partial_profile_count':report['partial_profiles'],'failed_input_count':report['failed_inputs'],'envelope_count':report['terminal_count'],'dataset_sha256':{f:file_hash(base/'data'/f) for f in ('entry-companies.jsonl','profiles.jsonl','envelopes.jsonl','source-manifest.jsonl')},'evaluator_command':'uv sync --frozen && uv run python -m aviscope.runner --organisations BATCH_FILE --output-dir out/official --history --max-cost 0','required_secret_environment_variables':[],'models':'none; deterministic extraction and synthesis','enabled_api':'Brreg public official APIs','expected_cost_per_official_run_usd':0,'cost_basis':'No chargeable provider enabled; measured official-data runs declare zero API spend.','reviewer_access':'pending; local source has not been pushed','readiness':{'implementation_complete':False,'local_validation_passed':integrity['passed'] and all(live_data['budget_checks'].values()),'submission_artifacts_complete':live_data['terminal_count']==live_data['input_count']==100,'reviewer_access_verified':False,'email_ready':False},'official_qualification':'not_determined','readiness_blockers':blockers,'refresh_scope':'Retained live submission corpus unchanged replay, not manufactured historical snapshots','evidence_directory':'data/evidence','email_sent':False}
    write_json(base/'submission-manifest.json',manifest)
    manifest['local_origin_url']=local_origin
    manifest['repository_url_status']='User-specified destination; remote lookup unsuccessful, existence and access unverified'
    manifest['enabled_sources']=['Brreg public official APIs','Registry-linked company websites subject to robots and exact-entity checks']
    write_json(base/'submission-manifest.json',manifest)
    checklist=(base/'SUBMISSION_CHECKLIST.md').read_text()+'\n## Generated measured status\n\n'+f"- Researched profiles: {report['researched_profiles']}; partial: {report['partial_profiles']}; failed: {report['failed_inputs']}.\n- Exact source: `{sha}`.\n- Live 100: {live_data['operations']['runtime_seconds']} seconds, {live_data['operations']['requests']} requests, $0 API spend.\n- Local data integrity: passed.\n- ZIP/extracted verification: see external package verification report; generated after archive construction.\n\n"+'\n'.join('- Pending: '+b for b in blockers)+'\n'
    (base/'SUBMISSION_CHECKLIST.md').write_text(checklist,encoding='utf-8')
    operations=live_data['operations']
    body=f'''DRAFT — NOT READY TO SEND

Hello Builderr team,

This draft accompanies an incomplete AviScope company-research entry for review. It is not yet a claim of a qualified or complete technical submission.

Agent name: AviScope
Entrant: Avinash
Contact for results: [VERIFIED CONTACT REQUIRED]
Repository URL: {remote}
Exact commit hash: {sha}
Repository access: Pending authorized push and reviewer-access verification.
Completed researched profile count: {report['researched_profiles']} (all partial profiles explicitly labelled; external coverage is not established).
Organisation-number manifest URL: Pending authorized publication; no accessible URL is claimed.
Organisation-number manifest in package: data/entry-companies.jsonl
Profiles and evidence: data/profiles.jsonl, data/envelopes.jsonl, data/source-manifest.jsonl, data/evidence/
Setup instructions: SUBMISSION_README.md and source/README.md
One-command run instruction (from source/, reviewer supplies input):
{manifest['evaluator_command']}

Models / APIs / licences: No model; Brreg public official APIs, NLOD 2.0 data attribution. See docs/MODELS_AND_APIS.md, docs/SOURCE_RIGHTS.md and source/NOTICE.md. Starter code redistribution terms need clarification.
Expected cost per 100-company run: $0 USD API spend with official APIs and permitted company-site fetches; no chargeable provider enabled.
Measured 100-company run: {operations['runtime_seconds']} seconds, {operations['requests']} outbound requests, ${operations['third_party_cost_usd']:.2f} API spend; local Windows hardware.
Refresh: --previous previous/profiles.jsonl; material output changes.jsonl; included refresh/ is a labelled unchanged replay of retained live sources.

Submission package proposed attachment: {stem}.zip
Checksum proposed attachment: {stem}.zip.sha256 (external; avoids a circular checksum)
Validation: locked dependencies, regression tests, financial JSON-pointer equality, exact input/output association, retained evidence hashing and fresh extracted package smoke. See reports/. No independent accuracy/recall or official qualification is claimed.

Outstanding blockers:
'''+'\n'.join('- '+b for b in blockers)+'''

This email is a draft only and must not be sent until the entry and access/contact details are ready.

Regards,
Avinash
[VERIFIED CONTACT REQUIRED]
'''
    (base/'email/submission-email.txt').write_text('To: submit@builderr.ai\nSubject: DRAFT — Signalpost Round 1 submission — AviScope — Avinash\n\n'+body,encoding='utf-8')
    mail=EmailMessage(policy=SMTP);mail['To']='submit@builderr.ai';mail['Subject']='DRAFT — Signalpost Round 1 submission — AviScope — Avinash';mail['X-Unsent']='1';mail.set_content(body)
    (base/'email/submission-email.eml').write_bytes(mail.as_bytes())
    clarification='''To: inquiries@builderr.ai
Subject: Signalpost entry — source access and contract clarification (draft)

Hello Builderr team,

Could you confirm the starter code redistribution licence; accepted read-only repository/artifact access and manifest URL alternatives; deadline time/timezone; external-family scoring weights; and whether cutoff constrains retrieval time or source effective/publication time? We have read the updated five-version allowance, sparse-pool rule and failed/missed-batch treatment. No submission is being sent by this draft.

JBOX bonus is not claimed. If we evaluate it later, please point us to official access documentation and any bonus-entry requirements.

Regards,
Avinash
'''
    (base/'email/clarification-draft.txt').write_text(clarification,encoding='utf-8')
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
    for name in ('submission-email.txt','submission-email.eml'):
        shutil.copyfile(base/'email'/name,dist/name)
    write_json(dist/'latest.json',{'zip':str(archive),'checksum':str(archive)+'.sha256','verification':str(dist/(stem+'-verification.json')),'manifest':str(base/'submission-manifest.json'),'submission_readme':str(base/'SUBMISSION_README.md'),'checklist':str(base/'SUBMISSION_CHECKLIST.md'),'email':str(dist/'submission-email.eml'),'source_commit':sha})
    print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':checksum,'verified':checked['passed'],'readiness':manifest['readiness']},indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default='out/submission');p.add_argument('--live-report',default='out/live-100/run-report.json');p.add_argument('--verify');args=p.parse_args()
    (ROOT/'dist').mkdir(exist_ok=True)
    if args.verify:print(json.dumps(verify(args.verify),indent=2))
    else:package(args.data_dir,args.live_report)


if __name__=='__main__':main()
