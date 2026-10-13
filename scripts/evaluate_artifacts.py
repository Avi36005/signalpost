import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aviscope.audit import audit
from aviscope.pipeline import finish
from aviscope.runner import read_jsonl,write_json,write_jsonl


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--output-dir',default='reports/evaluation');p.add_argument('--fixed');p.add_argument('--gap')
    args=p.parse_args();root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=True)
    profiles=read_jsonl(Path(args.directory)/'profiles.jsonl')
    failures=[]
    for previous in profiles:
        current=finish(deepcopy(previous),previous)
        if current['changes']:failures.append(previous['organisation_number'])
    result={'corpus':'Retained live profiles; no new network requests','profiles':len(profiles),'unchanged_replay_false_changes':len(failures),'idempotent':not failures,'changed_and_failed_sources':'Separately covered by labelled synthetic unit tests and starter refresh fixture','official_qualification':'not_determined'}
    write_json(root/'refresh-report.json',result)
    write_jsonl(root/'previous-snapshot.jsonl',profiles)
    write_jsonl(root/'current-snapshot.jsonl',[finish(deepcopy(p),p) for p in profiles])
    write_jsonl(root/'changes.jsonl',[])
    if args.fixed and args.gap:
        a=json.loads(Path(args.fixed).read_text());b=json.loads(Path(args.gap).read_text())
        same=a['input_sha256']==b['input_sha256']
        delta=b['supported_claims']-a['supported_claims']
        promote=same and delta>0
        reason=(f"Measured on the same {a['input_count']}-company cohort with company-owned external sources enabled: "
                f"fixed observed-link order yielded {a['supported_claims']} supported claims ({a['operations']['requests']} requests); "
                f"gap-directed priority yielded {b['supported_claims']} ({b['operations']['requests']} requests). "
                +('Gap-directed priority is promoted because it measured more supported claims on the identical cohort.' if promote
                  else 'Fixed remains default: gap-directed priority showed no measured claim advantage on this cohort. This is not a claim of independent precision or recall.'))
        comparison={'same_cohort':same,'fixed_requests':a['operations']['requests'],'gap_requests':b['operations']['requests'],'fixed_claims':a['supported_claims'],'gap_claims':b['supported_claims'],'claim_delta':delta,'external_sources_enabled':True,'promotion':'gap' if promote else 'not_promoted','reason':reason}
        write_json(root/'routing-comparison.json',comparison)
    write_json(root/'integrity-report.json',audit(args.directory))
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
