"""Deadline-safe completion: every input gets exactly one terminal envelope, in input order,
even when sources stall, fail or the batch is large. Fixtures use no network."""
import json
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from aviscope import runner
from aviscope.models import Profile
from aviscope.runner import parser, run, write_jsonl

ROOT = Path(__file__).resolve().parents[1]


def org_numbers(count, start=91_000_000):
    """Checksum-valid synthetic Norwegian organisation numbers (fixtures only, not real entities)."""
    out, base = [], start
    while len(out) < count:
        digits = f'{base:08d}'
        check = 11 - sum(int(x) * w for x, w in zip(digits, [3, 2, 7, 6, 5, 4, 3, 2])) % 11
        check = 0 if check == 11 else check
        if check != 10:
            out.append(digits + str(check))
        base += 1
    return out


def stub_profile(org):
    p = Profile(organisation_number=org).model_dump(mode='json')
    p['name'] = f'FIXTURE {org} AS'
    return p


def args_for(tmp_path, orgs, *extra):
    manifest = tmp_path / 'input.jsonl'
    write_jsonl(manifest, [{'organisation_number': o} for o in orgs])
    return parser().parse_args(['--organisations', str(manifest), '--output-dir', str(tmp_path / 'out'), '--expected-count', str(len(orgs)), *extra])


def read_envelopes(out):
    return [json.loads(line) for line in (out / 'envelopes.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]


@pytest.mark.parametrize('count', [100, 300, 1000, 1100])
def test_exact_cardinality_with_zero_request_budget(tmp_path, count):
    orgs = org_numbers(count)
    report = run(args_for(tmp_path, orgs, '--max-requests', '0', '--max-cost', '0'))
    envelopes = read_envelopes(tmp_path / 'out')
    assert report['terminal_count'] == count == len(envelopes)
    assert [e['organisation_number'] for e in envelopes] == orgs
    assert report['validation']['exact_cardinality'] and report['validation']['unique_association']
    assert report['operations']['requests'] == 0


@pytest.mark.parametrize('count', [300, 1100])
def test_failing_and_slow_sources_still_terminate_every_input(tmp_path, monkeypatch, count):
    orgs = org_numbers(count)
    failing = set(orgs[::7])

    def baseline(org, broker, frozen=None):
        if org in failing: raise ConnectionError('fixture: registry unavailable')
        time.sleep(.001)
        return stub_profile(org)

    def enrich(p, broker, routing='gap', history=False, guess=True):
        if int(p['organisation_number'][-3:]) % 5 == 0: raise TimeoutError('fixture: website timed out')
        return p

    monkeypatch.setattr(runner, 'baseline', baseline)
    monkeypatch.setattr(runner, 'enrich', enrich)
    report = run(args_for(tmp_path, orgs, '--max-requests', '0', '--max-cost', '0', '--max-seconds', '120'))
    envelopes = read_envelopes(tmp_path / 'out')
    assert [e['organisation_number'] for e in envelopes] == orgs
    assert report['deadline']['baseline_unfinished'] == 0 and report['deadline']['enrichment_unfinished'] == 0
    partial = (tmp_path / 'out' / 'envelopes.partial.jsonl').read_text(encoding='utf-8').splitlines()
    assert sorted(json.loads(x)['organisation_number'] for x in partial) == sorted(orgs)


def test_stalled_workers_cannot_hold_the_run_past_its_deadline(tmp_path, monkeypatch):
    orgs = org_numbers(60)
    release = threading.Event()
    stalled_baseline, stalled_enrich = set(orgs[:5]), set(orgs[5:15])

    def baseline(org, broker, frozen=None):
        if org in stalled_baseline: release.wait(120)
        return stub_profile(org)

    def enrich(p, broker, routing='gap', history=False, guess=True):
        if p['organisation_number'] in stalled_enrich: release.wait(120)
        return p

    monkeypatch.setattr(runner, 'baseline', baseline)
    monkeypatch.setattr(runner, 'enrich', enrich)
    started = time.monotonic()
    try:
        report = run(args_for(tmp_path, orgs, '--max-requests', '0', '--max-cost', '0', '--max-seconds', '6'))
        elapsed = time.monotonic() - started
    finally:
        release.set()
    assert elapsed < 6, elapsed
    envelopes = read_envelopes(tmp_path / 'out')
    assert [e['organisation_number'] for e in envelopes] == orgs
    assert report['deadline']['baseline_unfinished'] == 5
    assert report['deadline']['enrichment_unfinished'] == 10
    by_org = {e['organisation_number']: e for e in envelopes}
    profiles = {json.loads(l)['organisation_number']: json.loads(l) for l in (tmp_path / 'out' / 'profiles.jsonl').read_text(encoding='utf-8').splitlines()}
    assert any('official baseline completed' in e['reason'] for e in profiles[orgs[0]]['errors'])
    assert profiles[orgs[0]]['name'] is None and not profiles[orgs[0]]['claims']
    # Enrichment ran out of time: the official baseline is kept, the website families say why.
    assert profiles[orgs[5]]['name'] == f'FIXTURE {orgs[5]} AS'
    assert 'not proof of absence' in profiles[orgs[5]]['availability']['website']['reason']
    assert len(by_org) == len(orgs)


def test_process_exits_on_time_with_a_worker_stuck_in_a_network_call(tmp_path):
    """Measures real process exit: the interpreter would otherwise join a blocked executor thread."""
    orgs = org_numbers(20)
    manifest = tmp_path / 'input.txt'
    manifest.write_text('\n'.join(orgs) + '\n')
    script = tmp_path / 'harness.py'
    script.write_text(textwrap.dedent(f'''
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from aviscope import runner
        from aviscope.models import Profile
        def baseline(org, broker, frozen=None):
            if org == {orgs[3]!r}: time.sleep(600)   # simulates an unbounded DNS/TLS stall
            p = Profile(organisation_number=org).model_dump(mode='json'); p['name'] = 'FIXTURE'; return p
        runner.baseline = baseline
        runner.enrich = lambda p, *a, **k: p
        sys.argv = ['aviscope.runner', '--organisations', {str(manifest)!r}, '--output-dir', {str(tmp_path / 'out')!r},
                    '--max-requests', '0', '--max-cost', '0', '--max-seconds', '5']
        runner.main()
    '''))
    started = time.monotonic()
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr[-2000:]
    assert elapsed < 5 + 10, elapsed   # interpreter start-up + the 5 s run ceiling
    envelopes = read_envelopes(tmp_path / 'out')
    assert [e['organisation_number'] for e in envelopes] == orgs


def test_exhausted_budget_fails_fast_without_booking_throttle_slots(tmp_path):
    from aviscope.fetch import Broker, Budget, BudgetExceeded
    broker = Broker(tmp_path, Budget(max_requests=0))
    started = time.monotonic()
    for _ in range(50):
        with pytest.raises(BudgetExceeded):
            broker.fetch('https://data.brreg.no/enhetsregisteret/api/enheter/945811714')
    assert time.monotonic() - started < 1.0
    assert not broker.host_next   # no polite-host slot was consumed
