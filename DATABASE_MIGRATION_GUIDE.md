# Database Migration Guide / 数据库迁移指南

[English](#english) | [中文](#中文)

---

## English

This guide explains the new SQLite database system for mai-gen-videob50 and how to migrate from the existing JSON-based storage.

### Overview

The new database system replaces the JSON file-based storage with a SQLite database, providing:

- **Better Performance**: Faster queries and data operations
- **Data Integrity**: Foreign key constraints and proper data validation
- **Song Progress Tracking**: Track the same song across multiple archives/timestamps
- **Efficient Storage**: Normalized data structure reduces redundancy
- **Backward Compatibility**: Existing code continues to work with minimal changes

### Database Schema

#### Core Tables

1. **users** - User information and global settings
2. **save_archives** - Save archives (replaces timestamp-based folders)
3. **records** - Individual song records (B50 entries)
4. **video_configs** - Video configuration for each record
5. **video_search_results** - Search results from streaming platforms
6. **project_configs** - Intro/ending and global video settings
7. **assets** - Asset tracking (images, videos, etc.)

#### Key Relationships

- Users have multiple save archives
- Save archives contain multiple records
- Records can have video configurations and search results
- Assets are linked to records or archives

### Migration Process

#### 1. Scan Existing Data

```bash
# Scan existing JSON data structure
python test_migrate_database.py --scan-only
```

This will analyze your existing `b50_datas` directory and show:
- Number of users and archives
- Record counts and data structure
- Missing or corrupted files

#### 2. Run Test Migration

```bash
# Run test migration to verify everything works
python test_migrate_database.py --db-path test_migration.db
```

This creates a test database and verifies the migration process.

#### 3. Full Migration

```bash
# Run full migration (creates backup automatically)
python migrate_to_database.py
```

This will:
- Create a backup of existing JSON data
- Initialize the SQLite database
- Migrate all user data, archives, and configurations
- Verify the migration results

### Usage Examples

#### Basic Usage

```python
from utils.DatabaseDataHandler import DatabaseDataHandler

# Initialize handler
handler = DatabaseDataHandler()

# Save B50 data (same as before)
handler.save_b50_data("username", b50_data)

# Load B50 data (same as before)
data = handler.load_b50_data("username")

# Get user's save archives
archives = handler.get_user_save_list("username")
```

#### Song Progress Tracking

```python
from utils.DatabaseManager import DatabaseManager

db = DatabaseManager()

# Get user
user = db.get_user("username")

# Track progress for a specific song across all archives
history = db.get_song_history(user['id'], song_id="833", chart_type="DX", level_index=4)

# Get user progress summary
summary = db.get_user_progress_summary(user['id'])
```

#### Video Search Management

```python
# Save search results
handler.save_search_results("username", song_id, level_index, chart_type, "youtube", results)

# Get search results
results = handler.get_search_results("username", song_id, level_index, chart_type, "youtube")

# Update download status
handler.update_download_status("username", song_id, level_index, chart_type, "downloaded", video_path)
```

### Backward Compatibility

The new system provides backward compatibility functions that work exactly like the old JSON-based system:

```python
# These functions work without modification to existing code
from utils.DatabaseDataHandler import load_user_data, save_user_data, load_video_config, save_video_config

# Old code continues to work
data = load_user_data("username")
save_user_data("username", b50_data)
config = load_video_config("username")
save_video_config("username", video_config)
```

### Benefits

#### 1. Song Progress Tracking

Track how your scores improve over time:

```sql
-- Example: See progress on a specific song
SELECT sa.created_at, r.achievement, sa.rating 
FROM records r 
JOIN save_archives sa ON r.archive_id = sa.id 
WHERE r.song_id = '833' AND r.chart_type = 'DX' 
ORDER BY sa.created_at;
```

#### 2. Better Queries

Find patterns in your data:

```sql
-- Songs that appear in multiple archives
SELECT song_id, title, COUNT(*) as appearances 
FROM records 
GROUP BY song_id 
HAVING appearances > 1;
```

#### 3. Data Integrity

- Foreign key constraints prevent orphaned records
- NOT NULL constraints ensure required fields
- Proper data types prevent invalid data

#### 4. Performance

- Indexed queries for fast lookups
- Normalized structure reduces storage
- Efficient joins between related data

---

## 中文

本指南介绍了 mai-gen-videob50 的新 SQLite 数据库系统以及如何从现有的基于 JSON 的存储进行迁移。

### 概述

新的数据库系统用 SQLite 数据库替换了基于 JSON 文件的存储，提供：

- **更好的性能**：更快的查询和数据操作
- **数据完整性**：外键约束和适当的数据验证
- **歌曲进度跟踪**：跨多个存档/时间戳跟踪同一首歌曲
- **高效存储**：标准化数据结构减少冗余
- **向后兼容性**：现有代码继续工作，只需最少的更改

### 数据库架构

#### 核心表

1. **users** - 用户信息和全局设置
2. **save_archives** - 保存存档（替换基于时间戳的文件夹）
3. **records** - 单个歌曲记录（B50 条目）
4. **video_configs** - 每个记录的视频配置
5. **video_search_results** - 来自流媒体平台的搜索结果
6. **project_configs** - 片头/片尾和全局视频设置
7. **assets** - 资产跟踪（图片、视频等）

#### 关键关系

- 用户拥有多个保存存档
- 保存存档包含多个记录
- 记录可以有视频配置和搜索结果
- 资产链接到记录或存档

### 迁移过程

#### 1. 扫描现有数据

```bash
# 扫描现有的 JSON 数据结构
python test_migrate_database.py --scan-only
```

这将分析您现有的 `b50_datas` 目录并显示：
- 用户和存档的数量
- 记录计数和数据结构
- 丢失或损坏的文件

#### 2. 运行测试迁移

```bash
# 运行测试迁移以验证一切正常工作
python test_migrate_database.py --db-path test_migration.db
```

这会创建一个测试数据库并验证迁移过程。

#### 3. 完整迁移

```bash
# 运行完整迁移（自动创建备份）
python migrate_to_database.py
```

这将：
- 创建现有 JSON 数据的备份
- 初始化 SQLite 数据库
- 迁移所有用户数据、存档和配置
- 验证迁移结果

### 使用示例

#### 基本用法

```python
from utils.DatabaseDataHandler import DatabaseDataHandler

# 初始化处理器
handler = DatabaseDataHandler()

# 保存 B50 数据（与之前相同）
handler.save_b50_data("username", b50_data)

# 加载 B50 数据（与之前相同）
data = handler.load_b50_data("username")

# 获取用户的保存存档
archives = handler.get_user_save_list("username")
```

#### 歌曲进度跟踪

```python
from utils.DatabaseManager import DatabaseManager

db = DatabaseManager()

# 获取用户
user = db.get_user("username")

# 跨所有存档跟踪特定歌曲的进度
history = db.get_song_history(user['id'], song_id="833", chart_type="DX", level_index=4)

# 获取用户进度摘要
summary = db.get_user_progress_summary(user['id'])
```

#### 视频搜索管理

```python
# 保存搜索结果
handler.save_search_results("username", song_id, level_index, chart_type, "youtube", results)

# 获取搜索结果
results = handler.get_search_results("username", song_id, level_index, chart_type, "youtube")

# 更新下载状态
handler.update_download_status("username", song_id, level_index, chart_type, "downloaded", video_path)
```

### 向后兼容性

新系统提供向后兼容性函数，其工作方式与旧的基于 JSON 的系统完全相同：

```python
# 这些函数无需修改现有代码即可工作
from utils.DatabaseDataHandler import load_user_data, save_user_data, load_video_config, save_video_config

# 旧代码继续工作
data = load_user_data("username")
save_user_data("username", b50_data)
config = load_video_config("username")
save_video_config("username", video_config)
```

### 优势

#### 1. 歌曲进度跟踪

跟踪您的分数如何随时间改善：

```sql
-- 示例：查看特定歌曲的进度
SELECT sa.created_at, r.achievement, sa.rating 
FROM records r 
JOIN save_archives sa ON r.archive_id = sa.id 
WHERE r.song_id = '833' AND r.chart_type = 'DX' 
ORDER BY sa.created_at;
```

#### 2. 更好的查询

在您的数据中找到模式：

```sql
-- 出现在多个存档中的歌曲
SELECT song_id, title, COUNT(*) as appearances 
FROM records 
GROUP BY song_id 
HAVING appearances > 1;
```

#### 3. 数据完整性

- 外键约束防止孤立记录
- NOT NULL 约束确保必需字段
- 适当的数据类型防止无效数据

#### 4. 性能

- 索引查询实现快速查找
- 标准化结构减少存储
- 相关数据之间的高效连接

### 数据映射

#### JSON 到数据库字段映射

| JSON 字段 | 数据库字段 | 备注 |
|-----------|------------|------|
| `type` | `chart_type` | SD, DX, 宴, 协 |
| `achievements` | `achievement` | 分数百分比 |
| `dxScore` | `dx_score` | DX 分数值 |
| `ra` | `dx_rating` | 评级值 |
| `level` | `level_value` | 谱面难度 |

#### 存档结构

**旧结构：**
```
b50_datas/
├── username/
│   ├── 20250610_105924/
│   │   ├── b50_raw.json
│   │   ├── video_config.json
│   │   ├── images/
│   │   └── videos/
```

**新结构：**
- 所有数据存储在 SQLite 数据库中
- 存档通过基于时间戳的名称标识
- 资产在数据库中跟踪，包含文件路径
- 维护记录与其资产之间的关系

### 迁移验证

迁移后，验证您的数据：

1. **检查记录计数**：确保所有记录都已迁移
2. **验证关系**：检查记录是否链接到正确的存档
3. **测试查询**：运行示例查询以确保数据完整性
4. **备份验证**：确认备份已成功创建

### 故障排除

#### 常见问题

1. **缺少 b50_raw.json 文件**：这些存档将在迁移期间被跳过
2. **损坏的 JSON 数据**：检查迁移日志以获取具体错误
3. **字段映射问题**：某些旧数据格式可能需要手动调整

#### 恢复

如果迁移失败：
1. 从自动备份中恢复
2. 检查迁移日志以获取具体错误
3. 修复数据问题并重新运行迁移
4. 使用 `--verify-only` 标志检查数据库状态

### 文件结构变化

#### 迁移前
- 嵌套目录中的 JSON 文件
- 手动文件管理
- 无数据关系
- 难以跨存档查询

#### 迁移后
- 单个 SQLite 数据库文件
- 自动关系管理
- 轻松的跨存档查询
- 更好的数据组织

### 下一步

1. **测试新系统**与您现有的工作流程
2. **更新应用程序代码**以使用新的数据库功能
3. **考虑删除旧的 JSON 文件**在验证后
4. **探索新功能**如歌曲进度跟踪

新的数据库系统保持完全向后兼容性，同时为数据分析和管理提供强大的新功能。