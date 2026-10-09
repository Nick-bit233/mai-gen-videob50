"""Explicit real-OSS acceptance. Report writes occur only with --submit-test-report."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from utils.diagnostics import begin_report, package_report, upload_report, ReportUploadConflict
from utils.metadata_release import update_release


def check_report_policy(client, uploaded, endpoint, prefix, *, check_negative=False):
    """Probe only this synthetic report; never read a downloaded report body."""
    def status(response):
        try:
            return response.status_code
        finally:
            response.close()

    checks = {
        'get': status(client.get(uploaded['url'], timeout=30, allow_redirects=False, stream=True)),
        'head': status(client.head(uploaded['url'], timeout=30, allow_redirects=False)),
    }
    if check_negative:
        checks['list'] = status(client.get(endpoint, params={'list-type': '2', 'prefix': prefix.strip('/')+'/'},
                                          timeout=30, allow_redirects=False))
        checks['delete_synthetic_report'] = status(client.delete(uploaded['url'], timeout=30, allow_redirects=False))
        outside_key = 'outside-verification/'+uuid4().hex+'.txt'
        checks['outside_prefix_put'] = status(client.put(endpoint+'/'+outside_key, data=b'explicit permission test',
                                                        headers={'x-oss-forbid-overwrite': 'true'},
                                                        timeout=30, allow_redirects=False))
        checks['outside_test_key'] = outside_key
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata',action='store_true',help='Anonymously download/validate the configured release in an isolated directory')
    parser.add_argument('--submit-test-report',action='store_true',help='Upload one synthetic diagnostic package to the configured report prefix')
    parser.add_argument('--check-negative-policy',action='store_true',help='With a synthetic report, also check denied listing/deletion/outside-prefix write')
    args=parser.parse_args()
    if not args.metadata and not args.submit_test_report:
        parser.error('Choose --metadata or --submit-test-report explicitly')
    if args.check_negative_policy and not args.submit_test_report:
        parser.error('--check-negative-policy requires a synthetic report upload')
    output=ROOT/'test_output'/('release128-network-'+uuid4().hex)
    output.mkdir(parents=True)
    report=begin_report('1.2.8 真实网络验收',output/'diagnostics')
    summary={'status': 'running'}
    try:
        if args.metadata:
            config=json.loads((ROOT/'static/metadata_release_config.json').read_text(encoding='utf-8'))
            summary['metadata']=update_release(url=config['index_url'],files_root=config.get('files_root'),root=output/'metadata-workspace')
            if not summary['metadata']['updated']:
                raise RuntimeError(summary['metadata']['message'])
        if args.submit_test_report:
            config=json.loads((ROOT/'static/error_report_config.json').read_text(encoding='utf-8'))
            report.note('synthetic_report','This report contains no player data; created for explicit 1.2.8 network acceptance.')
            data=package_report(report.directory)
            endpoint=config['endpoint'].rstrip('/')
            prefix=config.get('prefix','reports')
            uploaded=upload_report(data,report.report_id,endpoint,prefix)
            summary['report']=uploaded
            client=requests.Session()
            client.trust_env=False
            try:
                checks=check_report_policy(client,uploaded,endpoint,prefix,check_negative=args.check_negative_policy)
                summary['negative_policy']=checks
                statuses={key:value for key,value in checks.items() if key != 'outside_test_key'}
                if not all(value in {401,403} for value in statuses.values()):
                    raise RuntimeError(f'Anonymous write-only policy check failed: {statuses}')
                summary['report']['anonymous_read_denied']=True
                try:
                    upload_report(data,report.report_id,endpoint,prefix)
                except ReportUploadConflict as exc:
                    if exc.object_key != uploaded['object_key']:
                        raise RuntimeError('Duplicate submission used a different object key') from exc
                    summary['report']['duplicate_upload_status']=409
                    summary['report']['duplicate_request_id']=exc.request_id
                else:
                    raise RuntimeError('Duplicate upload was not rejected; no-overwrite behavior is unverified')
            finally:
                client.close()
        summary['status']='passed'
    except Exception as exc:
        summary.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        (output/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'output':str(output),'checks':summary},ensure_ascii=False))


if __name__=='__main__':
    main()
