"""Explicit real-OSS acceptance. Report writes occur only with --submit-test-report."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils.diagnostics import begin_report, package_report, upload_report
from utils.metadata_release import update_release


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata',action='store_true',help='Anonymously download/validate the configured release in an isolated directory')
    parser.add_argument('--submit-test-report',action='store_true',help='Upload one synthetic diagnostic package to the configured report prefix')
    parser.add_argument('--check-negative-policy',action='store_true',help='With a synthetic report, check denied listing/deletion/outside-prefix write')
    args=parser.parse_args()
    if not args.metadata and not args.submit_test_report:
        parser.error('Choose --metadata or --submit-test-report explicitly')
    if args.check_negative_policy and not args.submit_test_report:
        parser.error('--check-negative-policy requires a synthetic report upload')
    output=ROOT/'test_output'/('release128-network-'+uuid4().hex)
    output.mkdir(parents=True)
    report=begin_report('1.2.8 真实网络验收',output/'diagnostics')
    summary={}
    if args.metadata:
        config=json.loads((ROOT/'static/metadata_release_config.json').read_text(encoding='utf-8'))
        summary['metadata']=update_release(url=config['index_url'],files_root=config.get('files_root'),root=output/'metadata-workspace')
        if not summary['metadata']['updated']:
            raise RuntimeError(summary['metadata']['message'])
    if args.submit_test_report:
        config=json.loads((ROOT/'static/error_report_config.json').read_text(encoding='utf-8'))
        report.note('synthetic_report','This report contains no player data; created for explicit 1.2.8 network acceptance.')
        data=package_report(report.directory)
        uploaded=upload_report(data,report.report_id,config['endpoint'],config.get('prefix','reports'))
        summary['report']=uploaded
        client=requests.Session()
        client.trust_env=False
        try:
            response=client.get(uploaded['url'],timeout=30,allow_redirects=False)
            assert response.status_code==200 and response.content==data,'Anonymous GET content mismatch'
            summary['report']['anonymous_read_verified']=True
            if args.check_negative_policy:
                endpoint=config['endpoint'].rstrip('/')
                prefix=config.get('prefix','reports').strip('/')
                listing=client.get(endpoint,params={'list-type':'2','prefix':prefix+'/'},timeout=30,allow_redirects=False)
                deletion=client.delete(uploaded['url'],timeout=30,allow_redirects=False)
                outside_key='outside-verification/'+uuid4().hex+'.txt'
                outside=client.put(endpoint+'/'+outside_key,data=b'explicit permission test',headers={'x-oss-forbid-overwrite':'true'},timeout=30,allow_redirects=False)
                negative={'list':listing.status_code,'delete_synthetic_report':deletion.status_code,'outside_prefix_put':outside.status_code,'outside_test_key':outside_key}
                summary['negative_policy']=negative
                assert all(value in {401,403} for value in (listing.status_code,deletion.status_code,outside.status_code)),negative
        finally:
            client.close()
    (output/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(output),'checks':summary},ensure_ascii=False))


if __name__=='__main__':
    main()
