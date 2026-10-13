from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import psutil

from .fetch import Broker, Budget
from .models import Profile, digest, now, org_number
from .pipeline import baseline, enrich, envelope, finish

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def write_jsonl(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        for row in rows: stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    temp.replace(path)


def read_jsonl(path, limit=10000):
    path = Path(path)
    if path.stat().st_size > 250_000_000: raise ValueError('Input file exceeds 250 MB')
    result = []
    with path.open(encoding='utf-8-sig') as stream:
        for line in stream:
            if not line.strip(): continue
            if len(line) > 10_000_000: raise ValueError('JSONL record too large')
            result.append(json.loads(line))
            if len(result) > limit: raise ValueError('Too many records')
    return result


def read_inputs(path):
    values = read_jsonl(path)
    orgs = [org_number(x.get('organisation_number') if isinstance(x, dict) else x) for x in values]
    if len(orgs) != len(set(orgs)): raise ValueError('Duplicate organisation numbers')
    return orgs


def file_hash(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_version():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        version_file = ROOT / 'SOURCE_VERSION'
        return version_file.read_text().strip() if version_file.exists() else None


def code_hash():
    return digest({p.relative_to(ROOT).as_posix(): file_hash(p) for p in sorted((ROOT/'aviscope').rglob('*.py'))})


def frozen_records(path, orgs, out, retrieved_at, cutoff):
    if not path: return {}
    if not retrieved_at: raise ValueError('--registry-retrieved-at is required for a supplied frozen registry; do not invent its retrieval time')
    if datetime.fromisoformat(retrieved_at.replace('Z', '+00:00')) > cutoff:
        raise ValueError('Frozen registry retrieval time is after cutoff')
    wanted = set(orgs); found = {}
    archive_hash = file_hash(path)
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    suffix = path.with_suffix('').suffix if path.suffix == '.gz' else path.suffix
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as stream:
        if suffix == '.csv':
            sample = stream.read(20000); stream.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            iterator = csv.DictReader(stream, dialect=dialect)
        else:
            iterator = (json.loads(line) for line in stream if line.strip())
        for row in iterator:
            org = str(row.get('organisasjonsnummer') or row.get('organisation_number') or '')
            if org not in wanted: continue
            if suffix == '.csv':
                canonical = {}
                for key, value in row.items():
                    if value == '' or value is None: continue
                    parts = key.split('.'); node = canonical
                    for part in parts[:-1]: node = node.setdefault(part, {})
                    if value.lower() in ('true', 'false'): value = value.lower() == 'true'
                    elif key == 'antallAnsatte': value = int(value)
                    node[parts[-1]] = value
                row = canonical
            if not row.get('organisasjonsnummer') or not row.get('navn'):
                raise ValueError('Frozen snapshot requires raw Brreg entity fields; eligible universe is not the identity snapshot')
            content = json.dumps(row, ensure_ascii=False, sort_keys=True).encode()
            sha = hashlib.sha256(content).hexdigest(); relative = 'evidence/' + sha + '.bin'
            (out/relative).parent.mkdir(parents=True, exist_ok=True); (out/relative).write_bytes(content)
            snap = {'id': 'sn-frozen-' + sha[:24], 'requested_url': 'https://data.brreg.no/enhetsregisteret/api/enheter/' + org, 'final_url': 'https://data.brreg.no/enhetsregisteret/api/enheter/' + org, 'redirect_chain': [], 'status': 200, 'content_type': 'application/json', 'retrieved_at': retrieved_at, 'content_sha256': sha, 'retained_sha256': sha, 'path': relative, 'source_class': 'official_registry', 'retention': 'permitted_open_data', 'frozen_archive_sha256': archive_hash, 'source_row_key': org}
            found[org] = (snap, row)
    return found


def parser():
    p = argparse.ArgumentParser(description='AviScope evaluator: exactly one terminal envelope per input')
    p.add_argument('--organisations', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--run-id', default=None)
    p.add_argument('--expected-count', type=int, default=100)
    p.add_argument('--bulk', help='Optional evaluator-supplied Brreg CSV/JSONL, optionally gzipped')
    p.add_argument('--registry-retrieved-at', help='Actual provenance timestamp for frozen snapshot')
    p.add_argument('--previous', help='Prior profiles.jsonl; relative evidence resolved beside it')
    p.add_argument('--cutoff', help='Latest permitted evidence retrieval timestamp, ISO UTC; defaults to run deadline')
    p.add_argument('--max-requests', type=int, default=2000)
    p.add_argument('--max-seconds', type=float, default=2600)
    p.add_argument('--max-cost', type=float, default=10)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--source-policy', default=str(ROOT/'config/sources.json'))
    p.add_argument('--routing', choices=('fixed', 'gap'), default='fixed')
    p.add_argument('--history', action='store_true', help='Fetch available filing years at <= 1 start / 2.1 seconds')
    p.add_argument('--resume', action='store_true')
    return p


def run(args, on_progress=None):
    if not 1 <= args.workers <= 8: raise ValueError('Workers must be 1..8')
    if args.max_requests < 0 or args.max_seconds <= 0 or args.max_cost < 0: raise ValueError('Invalid budget')
    orgs = read_inputs(args.organisations)
    if len(orgs) != args.expected_count: raise ValueError(f'Expected {args.expected_count} unique inputs, found {len(orgs)}')
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    lock_path = out / '.run.lock'
    if args.resume and lock_path.exists():
        old_pid = int(lock_path.read_text())
        if not psutil.pid_exists(old_pid):
            lock_path.unlink()
    lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(lock, str(os.getpid()).encode()); os.close(lock)
    try:
        return _run(args, orgs, out, on_progress)
    finally:
        lock_path.unlink(missing_ok=True)


def _run(args, orgs, out, on_progress):
    policy = json.loads(Path(args.source_policy).read_text(encoding='utf-8-sig'))
    previous = {p['organisation_number']: p for p in read_jsonl(args.previous)} if args.previous else {}
    if previous:
        previous_root = Path(args.previous).parent.resolve()
        for p in previous.values():
            Profile.model_validate(p)
            for s in p['source_snapshots']:
                if not s.get('path'): continue
                source = (previous_root / s['path']).resolve()
                target = (out / s['path']).resolve()
                if not source.is_relative_to(previous_root / 'evidence') or not target.is_relative_to(out.resolve() / 'evidence'):
                    raise ValueError('Unsafe prior evidence path')
                if source.exists() and source != target:
                    target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    settings = {'orgs': orgs, 'code_sha256': code_hash(), 'policy_sha256': digest(policy), 'routing': args.routing, 'history': args.history, 'cutoff': args.cutoff, 'bulk_hash': file_hash(args.bulk) if args.bulk else None, 'registry_retrieved_at': args.registry_retrieved_at, 'previous_hash': file_hash(args.previous) if args.previous else None, 'max_requests': args.max_requests, 'max_seconds': args.max_seconds, 'max_cost': args.max_cost}
    checkpoint = out/'checkpoint.json'
    if checkpoint.exists() and not args.resume: raise ValueError('Output already contains a run; choose a new directory or --resume')
    resumed = json.loads(checkpoint.read_text(encoding='utf-8')) if args.resume and checkpoint.exists() else None
    if resumed and resumed['settings'] != settings: raise ValueError('Resume requires exactly matching inputs, source, policies and budgets')
    run_id = resumed['run_id'] if resumed else args.run_id or 'aviscope-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    started_at = resumed['started_at'] if resumed else now()
    elapsed_before = max(resumed.get('elapsed_seconds', 0), (datetime.now(timezone.utc)-datetime.fromisoformat(started_at.replace('Z','+00:00'))).total_seconds()) if resumed else 0
    budget = Budget(args.max_requests, max(.001, args.max_seconds-elapsed_before), args.max_cost)
    journal = out/'requests.jsonl'
    if journal.exists():
        if not args.resume: raise ValueError('Existing request journal requires --resume')
        budget.requests = sum(1 for line in journal.read_text().splitlines() if line.strip())
    if resumed:
        budget.bytes = max(resumed.get('bytes', 0), budget.requests * 2_000_000)
    cutoff = datetime.fromisoformat(args.cutoff.replace('Z', '+00:00')) if args.cutoff else datetime.fromtimestamp(time.time()+budget.max_seconds, timezone.utc)
    if cutoff.tzinfo is None: raise ValueError('Cutoff requires timezone')
    budget.max_seconds = min(budget.max_seconds, max(.001, (cutoff-datetime.now(timezone.utc)).total_seconds()))
    frozen = frozen_records(args.bulk, orgs, out, args.registry_retrieved_at, cutoff)
    broker = Broker(out, budget, policy)
    state = resumed.get('profiles', {}) if resumed else {}
    done = set(resumed.get('done', [])) if resumed else set()
    phases = resumed.get('baseline_done', []) if resumed else []
    baseline_done = set(phases)
    process = psutil.Process(); peak = process.memory_info().rss
    stop = threading.Event()
    def monitor():
        nonlocal peak
        while not stop.wait(.1): peak = max(peak, process.memory_info().rss)
    monitor_thread = threading.Thread(target=monitor, daemon=True); monitor_thread.start()
    def save(phase):
        progress = {'run_id': run_id, 'phase': phase, 'total': len(orgs), 'baseline_completed': len(baseline_done), 'completed': len(done), 'operations': budget.metrics(), 'updated_at': now()}
        write_json(out/'progress.json', progress)
        write_json(checkpoint, {'settings': settings, 'run_id': run_id, 'started_at': started_at, 'elapsed_seconds': elapsed_before + time.monotonic()-budget.started, 'bytes': budget.bytes, 'baseline_done': sorted(baseline_done), 'done': sorted(done), 'profiles': state})
        if on_progress: on_progress(progress)
    save('official_baseline')
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            tasks = {pool.submit(baseline, org, broker, frozen.get(org, False) if args.bulk else None): org for org in orgs if org not in baseline_done}
            for future in as_completed(tasks):
                org = tasks[future]
                try:
                    state[org] = future.result()
                    if args.bulk and org not in frozen:
                        # Frozen identity source is authoritative. A missing row cannot silently fall back to live identity.
                        state[org] = Profile(organisation_number=org).model_dump(mode='json')
                        state[org]['errors'].append({'module': 'legal_identity', 'reason': 'Entity absent from evaluator frozen registry'})
                        state[org]['availability']['legal_identity'].update(state='failed', reason='Absent from supplied frozen registry')
                except Exception as exc:
                    state[org] = Profile(organisation_number=org).model_dump(mode='json')
                    state[org]['errors'].append({'module': 'runner', 'reason': type(exc).__name__ + ': ' + str(exc)[:200]})
                baseline_done.add(org)
                if len(baseline_done) % 10 == 0 or len(baseline_done) == len(orgs): save('official_baseline')
        # Everyone gets an official-data opportunity before any optional external/history requests.
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            tasks = {pool.submit(enrich, state[org], broker, args.routing, args.history): org for org in orgs if org not in done}
            for future in as_completed(tasks):
                org = tasks[future]
                try: state[org] = future.result()
                except Exception as exc: state[org]['errors'].append({'module': 'enrichment', 'reason': type(exc).__name__ + ': ' + str(exc)[:200]})
                state[org] = finish(state[org], previous.get(org)); done.add(org)
                if len(done) % 10 == 0 or len(done) == len(orgs): save('enrichment')
    finally:
        stop.set(); monitor_thread.join(timeout=1)
    profiles = [state[org] for org in orgs]
    envelopes = [envelope(p, run_id, started_at) for p in profiles]
    write_jsonl(out/'profiles.jsonl', profiles); write_jsonl(out/'envelopes.jsonl', envelopes)
    write_jsonl(out/'entry-companies.jsonl', [{'organisation_number': org} for org in orgs])
    write_jsonl(out/'changes.jsonl', [c for p in profiles for c in p['changes']])
    write_jsonl(out/'source-manifest.jsonl', list({s['id']: s for p in profiles for s in p['source_snapshots']}.values()))
    write_jsonl(out/'review-queue.jsonl', [q for p in profiles for q in p['review_queue']] + [{'organisation_number': p['organisation_number'], 'reason': 'Independent human exact-identity and claim-support review pending', 'claim_count': len(p['claims'])} for p in profiles])
    write_jsonl(out/'fetch-events.jsonl', broker.events)
    runtime = elapsed_before + time.monotonic()-budget.started
    timings = sorted(sum(p['operations'].get(k, 0) for k in ('baseline_seconds', 'enrichment_seconds')) for p in profiles)
    researched = sum(bool(p['name'] and any(not c['stale'] for c in p['claims'])) for p in profiles)
    fully_covered = sum(all(v['state'] == 'available' for v in p['availability'].values()) for p in profiles)
    disk = sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
    report = {'schema_version': 'aviscope-run-1', 'run_id': run_id, 'source_commit': source_version(), 'source_code_sha256': code_hash(), 'dependency_lock_sha256': file_hash(ROOT/'uv.lock'), 'input_sha256': file_hash(args.organisations), 'started_at': started_at, 'completed_at': now(), 'cutoff': cutoff.isoformat(), 'command': [sys.executable, '-m', 'aviscope.runner', *sys.argv[1:]], 'settings': settings, 'environment': {'python': platform.python_version(), 'platform': platform.platform(), 'workers': args.workers}, 'input_count': len(orgs), 'terminal_count': len(envelopes), 'unique_profiles': len(profiles), 'researched_profiles': researched, 'partial_profiles': researched-fully_covered, 'all_families_available_profiles': fully_covered, 'failed_inputs': len(orgs)-researched, 'supported_claims': sum(len(p['claims']) for p in profiles), 'fresh_claims': sum(sum(not c['stale'] for c in p['claims']) for p in profiles), 'operations': {**budget.metrics(), 'runtime_seconds': round(runtime, 3), 'peak_memory_bytes': peak, 'temporary_disk_bytes': disk, 'p50_company_seconds': timings[len(timings)//2] if timings else None, 'p95_company_seconds': timings[min(len(timings)-1, int(len(timings)*.95))] if timings else None}, 'field_coverage': {f: sum(p['availability'][f]['state'] == 'available' for p in profiles) for f in profiles[0]['availability']} if profiles else {}, 'validation': {'exact_cardinality': len(envelopes) == len(orgs), 'unique_association': [e['organisation_number'] for e in envelopes] == orgs, 'schema_validated': True}, 'quality_metrics': {'official_score': None, 'official_qualification': 'not_determined', 'external_exact_entity_precision': None, 'weighted_external_recall': None, 'independent_review': 'pending'}, 'budget_checks': {'requests': budget.requests <= args.max_requests, 'wall_time': runtime <= args.max_seconds + 10, 'memory': peak <= 16_000_000_000, 'temporary_disk': disk <= 10_000_000_000, 'cost': budget.cost <= args.max_cost}, 'snapshot_mode': 'evaluator_supplied' if args.bulk else 'live_development_registry', 'setup_downloads_included': False, 'setup_accounting': 'Requirements, universe and dependency downloads are separately recorded setup; no external company response cache loaded'}
    write_json(out/'run-report.json', report); save('completed')
    return report


def main():
    args = parser().parse_args()
    try:
        report = run(args)
    except (ValueError, FileExistsError) as exc:
        raise SystemExit(str(exc))
    print(json.dumps({k: report[k] for k in ('run_id', 'input_count', 'researched_profiles', 'partial_profiles', 'failed_inputs', 'operations', 'validation')}, indent=2))


if __name__ == '__main__': main()
