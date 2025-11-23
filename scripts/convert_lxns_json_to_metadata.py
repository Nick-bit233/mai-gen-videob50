"""
将落雪查分器获取的JSON文件转换为metadata格式
"""
import json
import os
import sys

def convert_lxns_json_to_metadata(input_file: str, output_file: str = None):
    """
    将落雪查分器API返回的JSON文件转换为metadata格式
    
    Args:
        input_file: 输入的JSON文件路径（从test_lxns_song_list_api获取）
        output_file: 输出的metadata文件路径（可选）
    """
    if output_file is None:
        output_file = "./music_metadata/chunithm/lxns_songs.json"
    
    print("=" * 60)
    print("转换落雪查分器JSON为Metadata格式")
    print("=" * 60)
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    print()
    
    # 读取输入文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✓ 成功读取输入文件")
    except Exception as e:
        print(f"✗ 读取输入文件失败: {e}")
        return False
    
    # 转换songs格式
    songs = data.get('songs', [])
    print(f"找到 {len(songs)} 首歌曲")
    print("正在转换格式...")
    
    converted_songs = []
    for song in songs:
        song_id = song.get('id')
        title = song.get('title', '')
        artist = song.get('artist', '')
        genre = song.get('genre', '')
        bpm = song.get('bpm', 0)
        version = song.get('version', 0)
        
        # 转换difficulties为sheets格式
        sheets = []
        difficulties = song.get('difficulties', [])
        
        for diff in difficulties:
            difficulty_index = diff.get('difficulty', 0)
            level_str = diff.get('level', '0')
            level_value = diff.get('level_value', 0.0)
            note_designer = diff.get('note_designer', '')
            diff_version = diff.get('version', version)
            
            # 将difficulty索引转换为level_label
            level_labels = ["BASIC", "ADVANCED", "EXPERT", "MASTER", "ULTIMA"]
            level_label = level_labels[difficulty_index] if difficulty_index < len(level_labels) else "EXPERT"
            
            sheet = {
                'difficulty': level_label,
                'level': level_str,
                'internalLevelValue': level_value,
                'noteDesigner': note_designer,
                'version': diff_version
            }
            sheets.append(sheet)
        
        metadata_song = {
            'id': song_id,
            'title': title,
            'artist': artist,
            'genre': genre,
            'bpm': bpm,
            'version': version,
            'sheets': sheets
        }
        converted_songs.append(metadata_song)
    
    # 构建metadata对象
    metadata = {
        'songs': converted_songs,
        'genres': data.get('genres', []),
        'versions': data.get('versions', []),
        'source': 'lxns',
        'api_endpoint': '/api/v0/chunithm/song/list'
    }
    
    # 保存到文件
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 转换成功!")
        print(f"  - 曲目数量: {len(converted_songs)}")
        print(f"  - 分类数量: {len(metadata['genres'])}")
        print(f"  - 版本数量: {len(metadata['versions'])}")
        print(f"\n文件已保存到: {output_file}")
        return True
    except Exception as e:
        print(f"\n✗ 保存文件失败: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法:")
        print(f"  python {os.path.basename(__file__)} <输入JSON文件> [输出文件路径]")
        print()
        print("示例:")
        print(f"  python {os.path.basename(__file__)} ../test_lxns_song_list_vdefault_notesFalse.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = convert_lxns_json_to_metadata(input_file, output_file)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ 转换完成!")
        print("=" * 60)
        print("\n现在可以在应用中使用此metadata文件了。")
    else:
        print("\n" + "=" * 60)
        print("✗ 转换失败")
        print("=" * 60)
        sys.exit(1)

