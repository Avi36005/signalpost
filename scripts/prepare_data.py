"""Reproduce universe verification and disjoint seeded local splits."""
import argparse
import gzip
import hashlib
import json
import random
import urllib.request
from pathlib import Path

ARCHIVE='1c89710e5b01f8617e86d09fbdff4a52f2f8dbbba297e74f7164b5984f5a0384'
CONTENT='b82d6a3e7231d1759a958c282bc4366b80ec2fab8095053d8ed7fa9cd01bc838'


def main():
    p=argparse.ArgumentParser();p.add_argument('--universe',default='downloads/universe.jsonl.gz');p.add_argument('--output-dir',default='data');p.add_argument('--seed',type=int,default=20260913)
    args=p.parse_args();path=Path(args.universe)
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen('https://builderr.ai/signalpost-company-universe-2025.jsonl.gz',timeout=120) as response: path.write_bytes(response.read())
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==ARCHIVE,'Archive mismatch'
    content=gzip.decompress(raw);assert hashlib.sha256(content).hexdigest()==CONTENT,'Content mismatch'
    rows=[json.loads(x) for x in content.splitlines() if x]
    assert len(rows)==411160 and len({r['organisation_number'] for r in rows})==411160
    random.Random(args.seed).shuffle(rows);out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    for name,subset in [('entry-companies',rows[:1000]),('development',rows[1000:1020]),('validation',rows[1020:1040]),('live-100',rows[1040:1140]),('smoke',rows[:10])]:
        (out/(name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in subset),encoding='utf-8')
    print(json.dumps({'universe_rows':len(rows),'archive_sha256':ARCHIVE,'content_sha256':CONTENT,'selection_seed':args.seed,'entry':1000,'development':20,'validation':20,'live_100':100,'group_separation':'not established'}))


if __name__=='__main__':main()
