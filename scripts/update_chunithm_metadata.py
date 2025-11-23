"""
更新中二节奏metadata脚本
从落雪查分器API获取曲目列表并保存为metadata文件
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lxns_metadata_loader import update_chunithm_metadata_from_lxns

if __name__ == "__main__":
    # 从环境变量或命令行参数获取API密钥
    api_key = os.getenv("LXNS_API_KEY", None)
    
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    
    print("=" * 60)
    print("中二节奏Metadata更新工具")
    print("=" * 60)
    print()
    
    if not api_key:
        print("提示: 可以通过以下方式提供API密钥:")
        print("  1. 环境变量: export LXNS_API_KEY='your_api_key'")
        print("  2. 命令行参数: python update_chunithm_metadata.py your_api_key")
        print()
        print("某些端点可能需要API密钥认证")
        print()
    
    # 更新metadata（不包含谱面物量，文件更小）
    success = update_chunithm_metadata_from_lxns(api_key=api_key, version=None, notes=False)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Metadata更新成功!")
        print("=" * 60)
        print("\n文件已保存到: ./music_metadata/chunithm/lxns_songs.json")
        print("\n现在可以在应用中使用此metadata文件了。")
    else:
        print("\n" + "=" * 60)
        print("✗ Metadata更新失败")
        print("=" * 60)
        print("\n请检查:")
        print("1. API密钥是否正确")
        print("2. 网络连接是否正常")
        print("3. 是否有写入权限")
        sys.exit(1)

