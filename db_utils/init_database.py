#!/usr/bin/env python3
"""
数据库初始化脚本
用于手动初始化或重置数据库

用法:
    python init_database.py              # 初始化数据库（如果不存在）
    python init_database.py --reset      # 重置数据库（删除后重新创建）
    python init_database.py --migrate    # 仅应用迁移（不重新创建）
"""

import os
import sys
import argparse

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from DatabaseManager import DatabaseManager

def init_database(db_path: str = "mai_gen_videob50.db", reset: bool = False, migrate_only: bool = False):
    """
    初始化数据库
    
    Args:
        db_path: 数据库文件路径
        reset: 是否重置数据库（删除后重新创建）
        migrate_only: 是否仅应用迁移（不重新创建）
    """
    print("=" * 60)
    print("数据库初始化工具")
    print("=" * 60)
    
    # 如果重置，先删除现有数据库
    if reset:
        if os.path.exists(db_path):
            print(f"\n⚠️  警告: 将删除现有数据库文件: {db_path}")
            try:
                os.remove(db_path)
                print(f"✅ 已删除现有数据库文件")
            except Exception as e:
                print(f"❌ 删除数据库文件失败: {e}")
                return False
        else:
            print(f"\nℹ️  数据库文件不存在，无需删除: {db_path}")
    
    # 创建数据库管理器（会自动初始化）
    try:
        print(f"\n📦 正在初始化数据库: {db_path}")
        db = DatabaseManager(db_path)
        
        if migrate_only:
            print("\n🔄 仅应用迁移...")
            db.check_and_apply_migrations()
        else:
            print("\n✅ 数据库初始化完成")
        
        # 检查数据库状态
        print("\n📊 数据库状态:")
        version = db.get_schema_version()
        print(f"   版本: {version}")
        
        # 检查表是否存在
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"   表数量: {len(tables)}")
            print(f"   表列表: {', '.join(tables)}")
        
        # 检查迁移状态
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        if os.path.exists(migrations_dir):
            migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.sql')])
            print(f"\n📝 迁移文件: {len(migration_files)} 个")
            for mf in migration_files:
                print(f"   - {mf}")
        
        print("\n" + "=" * 60)
        print("✅ 数据库初始化成功！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(
        description='数据库初始化工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python init_database.py                    # 初始化数据库（如果不存在）
  python init_database.py --reset            # 重置数据库（删除后重新创建）
  python init_database.py --migrate          # 仅应用迁移
  python init_database.py --db custom.db     # 使用自定义数据库路径
        """
    )
    
    parser.add_argument(
        '--db',
        type=str,
        default='mai_gen_videob50.db',
        help='数据库文件路径（默认: mai_gen_videob50.db）'
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='重置数据库（删除现有数据库后重新创建）'
    )
    
    parser.add_argument(
        '--migrate',
        action='store_true',
        dest='migrate_only',
        help='仅应用迁移（不重新创建数据库）'
    )
    
    args = parser.parse_args()
    
    # 获取数据库绝对路径
    db_path = args.db
    if not os.path.isabs(db_path):
        # 如果是相对路径，相对于项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        db_path = os.path.join(project_root, db_path)
    
    success = init_database(
        db_path=db_path,
        reset=args.reset,
        migrate_only=args.migrate_only
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

