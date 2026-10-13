"""Local-only workbench over the same evidence and profiles as the evaluator."""
from __future__ import annotations

import argparse
import json
import os
import threading
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import org_number
from .runner import ROOT, parser, read_jsonl, run, write_jsonl


class ResearchRequest(BaseModel):
    organisation_numbers: list[str] = Field(min_length=1, max_length=100)
    refresh: bool = False

    @field_validator('organisation_numbers')
    @classmethod
    def valid_orgs(cls, values):
        result = [org_number(v) for v in values]
        if len(set(result)) != len(result): raise ValueError('Duplicate organisation numbers')
        return result


def create_app(data_dir=None, work_dir=None):
    data = Path(data_dir or os.environ.get('AVISCOPE_DATA_DIR', 'out/submission')).resolve()
    work = Path(work_dir or 'out/workbench').resolve(); work.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title='AviScope', docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    jobs = {}; guard = threading.RLock(); cache = {}

    @app.middleware('http')
    async def local_controls(request: Request, call_next):
        if request.method not in ('GET', 'HEAD'):
            if int(request.headers.get('content-length', '0')) > 1_000_000:
                return JSONResponse({'detail': 'Request exceeds 1 MB'}, status_code=413)
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail': 'Cross-origin writes are disabled'}, status_code=403)
            if not request.headers.get('content-type', '').startswith('application/json'):
                return JSONResponse({'detail': 'JSON content type required'}, status_code=415)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    def directories():
        return [data] + sorted([x for x in work.iterdir() if x.is_dir()], key=lambda x: x.name)

    def profiles():
        found = {}
        for directory in directories():
            path = directory/'profiles.jsonl'
            if not path.exists(): continue
            stamp = path.stat().st_mtime_ns
            with guard:
                saved = cache.get(str(path))
                if not saved or saved[0] != stamp:
                    saved = (stamp, read_jsonl(path)); cache[str(path)] = saved
            for item in saved[1]:
                prior = found.get(item['organisation_number'])
                if not prior or item['researched_at'] >= prior['researched_at']:
                    found[item['organisation_number']] = item
        return found

    def profile(org):
        try: org_number(org)
        except ValueError as exc: raise HTTPException(422, str(exc))
        item = profiles().get(org)
        if not item: raise HTTPException(404, 'Company has not been researched yet')
        return item

    @app.get('/api/companies')
    def companies(q: str = '', page: int = 1, page_size: int = 25, availability: str = ''):
        page_size = max(1, min(page_size, 100)); page = max(1, page)
        selected = [p for p in profiles().values() if q.casefold() in ((p['name'] or '')+' '+p['organisation_number']).casefold()]
        if availability in ('financials', 'website', 'leadership', 'locations'):
            selected = [p for p in selected if p['availability'][availability]['state'] == 'available']
        selected.sort(key=lambda p: (p['name'] or '', p['organisation_number']))
        items = []
        for p in selected[(page-1)*page_size:page*page_size]:
            def get(field):
                matches = [c for c in p['claims'] if c['field'] == field and not c['stale'] and c['availability'] == 'available' and c['scope'] == 'legal_entity']
                return max(matches, key=lambda c: (c.get('period') or {}).get('tilDato', ''), default=None)
            items.append({'organisation_number': p['organisation_number'], 'name': p['name'], 'industry': get('industry'), 'employees': get('employees'), 'revenue': get('revenue'), 'researched_at': p['researched_at'], 'claims': len(p['claims']), 'availability': p['availability']})
        return {'items': items, 'total': len(selected), 'page': page, 'page_size': page_size}

    @app.get('/api/companies/{org}')
    def company(org: str): return profile(org)

    @app.get('/api/companies/{org}/evidence/{evidence_id}')
    def evidence(org: str, evidence_id: str):
        p = profile(org)
        record = next((e for e in p['evidence'] if e['id'] == evidence_id), None)
        if not record: raise HTTPException(404, 'Evidence receipt not found')
        snapshot = next((s for s in p['source_snapshots'] if s['content_sha256'] == record['content_sha256'] and s['final_url'] == record['source_url']), None)
        return {'evidence': record, 'snapshot': snapshot, 'claims': [c for c in p['claims'] if evidence_id in c['evidence_ids']]}

    @app.get('/api/changes')
    def changes():
        items = [c for p in profiles().values() for c in p['changes']]
        return {'items': sorted(items, key=lambda c: c['observed_at'], reverse=True)[:500]}

    @app.get('/api/runs')
    def runs():
        items = []
        for directory in directories():
            path = directory/'run-report.json'
            if path.exists(): items.append(json.loads(path.read_text(encoding='utf-8')))
        with guard: active = list(jobs.values())
        return {'items': items, 'active': active}

    @app.post('/api/research', status_code=202)
    def research(body: ResearchRequest):
        with guard:
            if any(j['state'] in ('queued', 'running') for j in jobs.values()):
                raise HTTPException(409, 'A research batch is already running; wait for it to finish')
            job_id = 'run-' + uuid.uuid4().hex[:12]
            directory = work/job_id; directory.mkdir()
            manifest = directory/'input.jsonl'
            write_jsonl(manifest, [{'organisation_number': org} for org in body.organisation_numbers])
            command = ['--organisations', str(manifest), '--output-dir', str(directory), '--expected-count', str(len(body.organisation_numbers)), '--run-id', job_id, '--max-requests', str(min(2000, len(body.organisation_numbers)*20))]
            if body.refresh:
                prior = [profiles()[org] for org in body.organisation_numbers if org in profiles()]
                # Copy only referenced evidence to the previous-state bundle used by the runner.
                previous_dir = directory/'previous'; previous_dir.mkdir()
                for p in prior:
                    for snap in p['source_snapshots']:
                        relative = snap.get('path')
                        if not relative: continue
                        for base in reversed(directories()):
                            origin = (base/relative).resolve()
                            target = (previous_dir/relative).resolve()
                            if not origin.is_relative_to(base/'evidence') or not target.is_relative_to(previous_dir/'evidence'):
                                continue
                            if origin.is_file():
                                import shutil
                                target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(origin, target); break
                previous_path = previous_dir/'profiles.jsonl'; write_jsonl(previous_path, prior)
                command.extend(['--previous', str(previous_path)])
            jobs[job_id] = {'id': job_id, 'state': 'queued', 'total': len(body.organisation_numbers), 'completed': 0}
        def execute():
            with guard: jobs[job_id]['state'] = 'running'
            def progress(update):
                with guard: jobs[job_id].update(update)
            try:
                run(parser().parse_args(command), on_progress=progress)
                with guard: jobs[job_id]['state'] = 'completed'
            except Exception as exc:
                with guard: jobs[job_id].update(state='failed', error=type(exc).__name__ + ': ' + str(exc)[:200])
        threading.Thread(target=execute, daemon=True).start()
        return {'run_id': job_id}

    @app.get('/api/health')
    def health(): return {'status': 'ok', 'agent': 'AviScope', 'mode': 'local', 'models': 'none'}

    @app.get('/')
    def index(): return FileResponse(ROOT/'web/index.html')
    app.mount('/static', StaticFiles(directory=ROOT/'web'), name='static')
    return app


def main():
    p = argparse.ArgumentParser(); p.add_argument('--data-dir', default='out/submission'); p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    uvicorn.run(create_app(args.data_dir), host='127.0.0.1', port=args.port)


if __name__ == '__main__': main()
