"""Prepare a desktop public projection locally; no OSS credentials or uploads."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.metadata_release import FILES, validate_charts, normalize_charts
from utils.video_metadata import build_desktop_manifest

SONG_FIELDS = ('id_fish','id_fish_dx','id_lx','id_otoge','title','title_kana','artist','genre','version','bpm',
               'image_code_otoge','image_code_dxrating','has_dx','aliases','wiki_url','charts_info')
CHART_FIELDS = ('type','difficulty','level_cn','level_latest','level_value_cn','level_value_latest','note_designer','version','note_counts')


def export_release(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.is_relative_to(source):
        raise ValueError('公开投影应输出到独立目录，不能覆盖私有 release。')
    if output.exists():
        raise ValueError('输出目录已存在，请选择新的目录。')
    descriptor = json.loads((source/'release.json').read_text(encoding='utf-8'))
    fusion = json.loads((source/FILES['chart_metadata']).read_text(encoding='utf-8'))
    raw = json.loads((source/FILES['asset_manifest']).read_text(encoding='utf-8'))
    charts = normalize_charts([{k:v for k,v in song.items() if k in SONG_FIELDS} for song in fusion])
    for song in charts:
        song['charts_info'] = [{k:v for k,v in chart.items() if k in CHART_FIELDS} for chart in song['charts_info']]
    identities = validate_charts(charts)
    manifest = build_desktop_manifest(raw)
    for asset in manifest['assets']:
        asset['source_url'] = f"https://www.bilibili.com/video/{asset['source_id']}?p={asset['source_pid']}"
    revision = descriptor['release_revision']
    if descriptor['metadata_store_version'] != manifest['metadata_store_version'] or raw.get('release_revision', revision) != revision:
        raise ValueError('源文件的 release 版本不一致。')
    if any((a['song_title'],a['artist'],a['chart_type'],a['difficulty']) not in identities for a in manifest['assets']):
        raise ValueError('公开视频来源不能匹配到同版本谱面。')
    public_descriptor = {k:descriptor.get(k) for k in ('schema_version','game_type','release_revision','metadata_store_version')}
    public_descriptor['files'] = FILES
    output.mkdir(parents=True)
    for filename, payload in ((FILES['chart_metadata'],charts),(FILES['asset_manifest'],manifest),('release.json',public_descriptor)):
        (output/filename).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'release_revision':revision,'metadata_store_version':manifest['metadata_store_version'],
            'usable_assets':len(manifest['assets']), 'output':str(output)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(export_release(args.source,args.output),ensure_ascii=False))


if __name__ == '__main__':
    main()
