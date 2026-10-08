"""Actual embedded-Python isolation and damaged-runtime diagnostics."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--application',required=True,type=Path)
    args=parser.parse_args()
    root=args.application.resolve()
    if not root.name.startswith('release128'):
        parser.error('Use a release128 acceptance copy')
    output=root/'startup-acceptance'
    output.mkdir(exist_ok=False)
    foreign=output/'foreign Python'
    foreign.mkdir()
    (foreign/'_distutils_hack.py').write_text("raise RuntimeError('foreign Python was imported')",encoding='utf-8')
    (foreign/'streamlit.py').write_text("raise RuntimeError('foreign streamlit was imported')",encoding='utf-8')
    environment=dict(os.environ,PYTHONHOME=str(foreign),PYTHONPATH=str(foreign),PYTHONUSERBASE=str(foreign),USERPROFILE=str(root/'test-home'))
    environment['PATH']=str(Path(shutil.which('python')).parent)+';'+environment['PATH']
    python=root/'runtime/python.exe'
    code=f"import sys,pathlib,importlib.util,json; sys.path.insert(0,{str(root)!r}); import runtime_bootstrap; runtime_bootstrap.preflight(pathlib.Path({str(root)!r})); print(json.dumps({{'executable':sys.executable,'isolated':sys.flags.isolated,'no_user_site':sys.flags.no_user_site,'hack_origin':importlib.util.find_spec('_distutils_hack').origin}}))"
    result=subprocess.run([str(python),'-I','-X','utf8','-c',code],cwd=foreign,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert result.returncode==0,result.stderr
    normal=json.loads(result.stdout.splitlines()[-1])
    assert normal['isolated']==1 and normal['no_user_site']==1
    assert Path(normal['hack_origin']).is_relative_to(root/'runtime')
    results={'foreign_python_isolated':normal,'negative_cases':[]}
    for case in ('missing-hack','missing-pth'):
        sample=output/case
        runtime=sample/'runtime'
        runtime.mkdir(parents=True)
        for source in (root/'runtime').iterdir():
            if source.is_file() and source.suffix in {'.exe','.dll','.pyd','.zip'}:
                shutil.copy2(source,runtime/source.name)
        if case=='missing-hack':
            shutil.copy2(root/'runtime/python312._pth',runtime/'python312._pth')
            (runtime/'Lib/site-packages').mkdir(parents=True)
        shutil.copy2(root/'runtime_bootstrap.py',sample/'runtime_bootstrap.py')
        (sample/'st_app.py').write_text('# acceptance fixture',encoding='utf-8')
        broken=subprocess.run([str(runtime/'python.exe'),'-I','-X','utf8',str(sample/'runtime_bootstrap.py')],env=environment,cwd=foreign,capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert broken.returncode!=0,case
        expected='_distutils_hack' if case=='missing-hack' else '_pth'
        assert expected in broken.stderr,broken.stderr
        logs=list((sample/'logs/startup').glob('*-error.txt'))
        assert logs and expected in logs[0].read_text(encoding='utf-8')
        results['negative_cases'].append({'case':case,'returncode':broken.returncode,'diagnostic':str(logs[0])})
    (root/'release128-startup-verification.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False))


if __name__=='__main__':
    main()
