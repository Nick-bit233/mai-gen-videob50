# TextRenderer 文字渲染模块重构计划

> 文档版本: v1.1
> 创建日期: 2026-03-02
> 更新日期: 2026-03-02
> 状态: 待审核

## 1. 需求背景

### 1.1 现有问题

当前 `utils/VideoUtils.py` 中的 `edit_game_text_clip` 函数使用 MoviePy 的 `TextClip` 组件直接渲染文字。存在以下问题：

1. **排版不美观** - MoviePY TextClip 的排版控制能力有限
2. **高级功能缺失** - 难以支持复杂的文字效果和精确的布局控制
3. **多语言支持不足** - 换行算法简单，无法智能断句

### 1.2 重构目标

将文字渲染逻辑从 MoviePy TextClip 迁移到自定义的图片渲染方案：

- 文字先渲染为 PNG 透明图片
- 再作为图片图层叠加到视频中
- 支持高级排版和样式功能

---

## 2. 功能需求清单

| # | 需求 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | PNG 透明背景输出 | P0 | 核心功能 |
| 2 | 自定义字体/字号/颜色 | P0 | 基础样式 |
| 3 | 文字描边 | P0 | 支持颜色和宽度 |
| 4 | 图片尺寸/边距/对齐 | P0 | 布局控制 |
| 5 | 行距控制 | P1 | 排版美观 |
| 6 | 智能换行（中英日） | P0 | 核心功能 |
| 7 | 手动换行符/制表符 | P1 | 兼容性 |
| 8 | 自动缩放字号 | P1 | 溢出处理 |
| 9 | Emoji 支持 | P1 | Unicode emoji |
| 10 | 保存到文件 + 内存变量 | P0 | 灵活输出 |

---

## 3. 技术方案选型

### 3.1 核心技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **文字渲染** | Pillow (PIL) | 成熟稳定、已在项目中使用、无需额外依赖 |
| **字体处理** | Pillow ImageFont + TrueType | 支持自定义字体、多语言 |
| **Emoji 支持** | 支持 emoji 的字体（如 Noto Color Emoji） | 无需额外库，依赖字体能力 |
| **中文分词** | jieba | 最流行的中文分词库，准确、轻量、支持自定义词典 |
| **日文分词** | tinysegmenter (可选) | 纯 Python 实现，轻量；或使用字符级断句 |

### 3.2 方案对比

#### 方案 A：Pillow（推荐）

**优点：**
- 项目已依赖 Pillow，无需新增依赖
- API 成熟稳定，文档完善
- 支持透明背景、描边、自定义字体
- 性能足够（渲染静态图片）

**缺点：**
- Emoji 渲染依赖字体支持（需要使用支持 emoji 的字体）
- 描边效果需要手动实现多层绘制

#### 方案 B：Cairo (pycairo)

**优点：**
- 渲染质量更高
- 原生支持复杂文字布局

**缺点：**
- 需要安装系统级依赖（libcairo）
- 增加部署复杂度
- 学习成本较高

#### 方案 C： aggdraw

**优点：**
- Pillow 扩展，渲染质量好

**缺点：**
- 维护不活跃
- 安装可能有兼容性问题

### 3.3 最终方案

**选择 Pillow 方案**，理由：
1. 项目已依赖，零额外成本
2. 功能满足所有需求
3. 部署简单，跨平台兼容

---

## 4. 智能断句算法设计

### 4.1 核心概念：断点 vs 不可断点

智能断句的核心是识别文本中的**可断点（Break Opportunity）**：

```
"大家好，欢迎来到这里"

❌ 错误断句：大|家好，欢迎|来到这里   （在词语中间断开）
✅ 正确断句：大家|好，|欢迎|来到|这里   （在词语边界断开）
```

### 4.2 分词策略

不同语言采用不同的分词策略：

| 语言 | 分词方式 | 工具/方法 | 示例 |
|------|----------|-----------|------|
| **中文** | 词级别分词 | jieba | "大家好" → ["大家", "好"] |
| **日文** | 词级别分词 | tinysegmenter（可选）或字符级 | "こんにちは" → ["こん", "にち", "は"] |
| **英文** | 空格分词 | 内置 split() | "Hello World" → ["Hello", "World"] |
| **韩文** | 字符级 | 按 Unicode 音节 | "안녕하세요" → ["안", "녕", "하", "세", "요"] |
| **数字** | 整体保持 | 正则识别 | "12345" → ["12345"] |
| **Emoji** | 整体保持 | Unicode 识别 | "😊" → ["😊"] |

### 4.3 中文分词详细设计（jieba）

#### 4.3.1 为什么选择 jieba

| 特性 | 说明 |
|------|------|
| **准确性** | 基于前缀词典 + 隐马尔可夫模型，准确率高 |
| **轻量** | 纯 Python 实现，无外部依赖 |
| **自定义词典** | 支持添加领域专用词汇（如音游术语） |
| **三种模式** | 精确模式、全模式、搜索引擎模式 |
| **广泛使用** | GitHub 33k+ stars，中文 NLP 标准选择 |

#### 4.3.2 使用方式

```python
import jieba

# 精确模式（推荐）- 将句子最精确地切开
text = "大家好，欢迎来到这里"
words = jieba.lcut(text)
# ['大家', '好', '，', '欢迎', '来到', '这里']

# 自定义词典 - 添加音游相关词汇
jieba.add_word("舞萌DX")
jieba.add_word("中二节奏")
jieba.add_word("谱面确认")
```

#### 4.3.3 自定义词典规划

针对本项目（音游视频生成），建议添加以下词汇：

```
# custom_dict.txt
舞萌DX 5 n
中二节奏 5 n
谱面确认 5 n
分表 5 n
B50 5 n
DX Rating 5 n
AP 5 n
FC 5 n
全连 5 n
收歌 5 v
推分 5 v
```

### 4.4 日文分词设计

#### 4.4.1 方案选择

| 方案 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **tinysegmenter** | 纯 Python，轻量 | 准确率一般 | ⭐⭐⭐ |
| **fugashi + MeCab** | 准确率高 | 需安装 MeCab | ⭐⭐ |
| **字符级断句** | 无依赖 | 可能断在不自然位置 | ⭐⭐⭐ |

#### 4.4.2 推荐：字符级 + 标点断句

考虑到项目复杂度和日文文本的实际情况，推荐采用**字符级断句 + 标点强制断点**：

```python
def segment_japanese(text: str) -> List[str]:
    """日文分词：字符级 + 标点断点"""
    result = []
    current = ""
    punctuations = "。、！？…」「』『【】（）"

    for char in text:
        current += char
        # 标点处强制断点
        if char in punctuations:
            if current:
                result.append(current)
                current = ""

    if current:
        result.append(current)

    return result
```

### 4.5 完整断句算法流程

```
输入文本
    ↓
┌─────────────────────────────────────┐
│  Step 1: 预处理                      │
│  - 识别并保留手动换行符 \n           │
│  - 识别并保留制表符 \t               │
│  - 按 \n 分割为多个段落              │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Step 2: 语言检测与分词              │
│  对每个段落：                        │
│  - 检测主要语言（中/日/英/混合）     │
│  - 中文 → jieba.lcut()              │
│  - 日文 → 字符级 + 标点断点          │
│  - 英文 → split()                   │
│  输出：词语列表 [word1, word2, ...]  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Step 3: 行构建                      │
│  初始化：current_line = ""          │
│  遍历词语列表：                      │
│  - 计算加入该词后的行宽度            │
│  - 如果超过 max_width：             │
│    → 输出 current_line 为一行       │
│    → current_line = 当前词          │
│  - 否则：                            │
│    → current_line += 当前词         │
└─────────────────────────────────────┘
    ↓
输出：行列表 ["第一行", "第二行", ...]
```

### 4.6 算法伪代码

```python
class TextWrapper:
    """智能文本换行器"""

    def __init__(self, font: ImageFont, max_width: int):
        self.font = font
        self.max_width = max_width

    def wrap(self, text: str) -> List[str]:
        """将文本换行为多行"""
        # Step 1: 按手动换行符分割
        paragraphs = text.split('\n')

        all_lines = []
        for para in paragraphs:
            if not para.strip():
                all_lines.append("")
                continue

            # Step 2: 分词
            words = self._tokenize(para)

            # Step 3: 构建行
            lines = self._build_lines(words)
            all_lines.extend(lines)

        return all_lines

    def _tokenize(self, text: str) -> List[str]:
        """分词：根据文本语言选择策略"""
        tokens = []
        i = 0

        while i < len(text):
            char = text[i]

            # Emoji 处理
            if self._is_emoji(char):
                emoji, length = self._extract_emoji(text, i)
                tokens.append(emoji)
                i += length

            # 空格/制表符
            elif char in ' \t':
                tokens.append(char)
                i += 1

            # 标点符号（单独成词）
            elif self._is_punctuation(char):
                tokens.append(char)
                i += 1

            # 中文字符 → 使用 jieba
            elif self._is_chinese(char):
                chinese_text, length = self._extract_chinese(text, i)
                tokens.extend(jieba.lcut(chinese_text))
                i += length

            # 日文字符 → 字符级分词
            elif self._is_japanese(char):
                japanese_text, length = self._extract_japanese(text, i)
                tokens.extend(self._segment_japanese(japanese_text))
                i += length

            # 英文/数字
            elif char.isascii():
                word, length = self._extract_ascii_word(text, i)
                tokens.append(word)
                i += length

            else:
                tokens.append(char)
                i += 1

        return tokens

    def _build_lines(self, words: List[str]) -> List[str]:
        """将词语列表构建为行"""
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + word
            width = self.font.getlength(test_line)

            if width <= self.max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines
```

### 4.7 断点规则总结

| 规则 | 描述 | 示例 |
|------|------|------|
| **词边界可断** | 分词后的词语边界是合法断点 | "大家\|好" ✅ |
| **词语内部不可断** | 单个词语内部不应断开 | "大\|家" ❌ |
| **标点后可断** | 标点符号后是合法断点 | "你好，\|欢迎" ✅ |
| **标点前不可断** | 标点符号不应与前面内容分离 | "你好\|，" ❌ |
| **数字整体** | 连续数字作为一个整体 | "123\|456" ❌ |
| **Emoji 整体** | Emoji 作为一个整体 | "😊" 不可拆分 |
| **手动换行优先** | \n 强制换行 | "第一行\n第二行" → 两行 |

### 4.8 混合文本处理示例

```
输入: "大家好！欢迎玩舞萌DX，这是一款非常有趣的音乐游戏😊"

分词结果:
['大家', '好', '！', '欢迎', '玩', '舞萌DX', '，', '这', '是', '一款', '非常', '有趣', '的', '音乐', '游戏', '😊']

假设 max_width 允许每行约 15 个字符宽度：

换行结果:
第1行: "大家好！欢迎玩舞萌DX，"
第2行: "这是一款非常有趣的音乐游戏"
第3行: "😊"
```

### 4.9 性能考虑

| 优化点 | 方案 |
|--------|------|
| **jieba 初始化** | 模块加载时初始化，避免重复加载词典 |
| **自定义词典** | 只加载一次，作为类变量缓存 |
| **长文本** | 对于超长文本，可考虑分批处理 |
| **缓存** | 相同文本 + 相同宽度可缓存换行结果 |

---

## 5. 模块设计

### 5.1 文件结构

```
utils/
├── TextRenderer.py      # 新增：文字渲染模块
├── VideoUtils.py        # 修改：调用 TextRenderer
└── ...
```

### 5.2 TextRenderer 类设计

```python
# utils/TextRenderer.py

from dataclasses import dataclass
from typing import Tuple, Optional, List, Union
from PIL import Image, ImageDraw, ImageFont
import os

@dataclass
class TextStyle:
    """文字样式配置"""
    font_path: str                    # 字体文件路径
    font_size: int = 24               # 字号
    color: str = "#FFFFFF"            # 文字颜色 (十六进制)
    stroke_color: Optional[str] = None  # 描边颜色
    stroke_width: int = 0             # 描边宽度

@dataclass
class LayoutConfig:
    """布局配置"""
    width: int = 800                  # 图片宽度
    height: int = 600                 # 图片高度（auto 时忽略）
    auto_height: bool = True          # 自动计算高度
    padding: Tuple[int, int, int, int] = (20, 20, 20, 20)  # 上右下左边距
    line_spacing: int = 8             # 行距
    horizontal_align: str = "left"    # 水平对齐: left/center/right
    vertical_align: str = "top"       # 垂直对齐: top/center/bottom

class TextRenderer:
    """文字渲染器 - 将文字渲染为透明 PNG 图片"""
    
    def __init__(self, style: TextStyle, layout: LayoutConfig):
        self.style = style
        self.layout = layout
        self._font = None
    
    def render(self, text: str) -> Image.Image:
        """渲染文字为 PIL Image 对象"""
        pass
    
    def render_to_file(self, text: str, output_path: str) -> str:
        """渲染文字并保存为 PNG 文件"""
        pass
    
    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """智能换行处理"""
        pass
    
    def _calculate_text_size(self, lines: List[str]) -> Tuple[int, int]:
        """计算文本所需尺寸"""
        pass
    
    def _auto_scale_font(self, text: str) -> int:
        """自动缩放字号以适应容器"""
        pass

def render_text_to_image(
    text: str,
    font_path: str,
    output_path: Optional[str] = None,
    **kwargs
) -> Union[Image.Image, Tuple[Image.Image, str]]:
    """便捷函数：渲染文字为图片"""
    pass
```

### 5.3 VideoUtils.py 改动

```python
# 修改 edit_game_text_clip 函数

from utils.TextRenderer import TextRenderer, TextStyle, LayoutConfig

def edit_game_text_clip(game_type, clip_config, resolution, style_config):
    """抽象出的文字处理函数，返回 (ImageClip, position)"""
    
    # 构建样式配置
    style = TextStyle(
        font_path=style_config['asset_paths']['comment_font'],
        font_size=style_config['content_text_style']['font_size'],
        color=style_config['content_text_style']['font_color'],
        stroke_color=style_config['content_text_style'].get('stroke_color') 
            if style_config['content_text_style'].get('enable_stroke') else None,
        stroke_width=style_config['content_text_style'].get('stroke_width', 0)
    )
    
    # 构建布局配置
    layout = LayoutConfig(
        width=...,
        padding=(20, 20, 20, 20),
        line_spacing=style_config['content_text_style']['interline'],
        horizontal_align=style_config['content_text_style']['horizontal_align'],
        vertical_align="top",
        auto_height=True
    )
    
    # 渲染文字为图片
    renderer = TextRenderer(style, layout)
    text_image = renderer.render(clip_config.get('text', ''))
    
    # 转换为 MoviePy ImageClip
    txt_clip = ImageClip(np.array(text_image)).with_duration(clip_config.get('duration', 5))
    
    # 计算位置...
    return txt_clip, text_pos
```

---

## 6. 依赖清单

### 6.1 新增依赖

| 包名 | 版本要求 | 用途 | 必需性 |
|------|----------|------|--------|
| **jieba** | >=0.42.1 | 中文分词 | ✅ 必需 |
| **tinysegmenter** | >=0.4 | 日文分词（可选） | ⭕ 可选 |

### 6.2 现有依赖（无需新增）

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| Pillow | >=10.4.0 | 图片渲染（已在 requirements.txt） |
| numpy | >=1.18.1 | 数组处理（已在 requirements.txt） |

### 6.3 requirements.txt 更新

```diff
+ jieba>=0.42.1
+ tinysegmenter>=0.4  # 可选，日文分词
```

### 6.4 字体要求

为支持 Emoji，建议在 `static/assets/fonts/` 目录添加：
- `NotoColorEmoji.ttf` 或
- `SegoeUIEmoji.ttf`（Windows 系统字体）

或使用系统字体路径：
- Linux: `/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf`
- macOS: `/System/Library/Fonts/Apple Color Emoji.ttc`
- Windows: `C:\Windows\Fonts\seguiemj.ttf`

---

## 7. 实现步骤

### Phase 1：基础框架（2-3 小时）

1. 创建 `utils/TextRenderer.py` 文件
2. 实现 `TextStyle` 和 `LayoutConfig` 数据类
3. 实现基础的 `TextRenderer` 类框架
4. 实现简单文字渲染（无换行、无描边）
5. 添加 jieba 到 requirements.txt

### Phase 2：分词模块（3-4 小时）

1. 实现 Unicode 字符类型识别函数
   - `_is_chinese(char)` - 中文字符判断
   - `_is_japanese(char)` - 日文字符判断
   - `_is_emoji(char)` - Emoji 判断
   - `_is_punctuation(char)` - 标点判断

2. 实现文本分词器 `TextTokenizer` 类
   - 集成 jieba 中文分词
   - 实现日文字符级分词
   - 实现英文空格分词
   - 处理混合文本

3. 创建自定义词典文件 `custom_dict.txt`
   - 添加音游相关词汇

4. 分词模块单元测试

### Phase 3：智能换行（2-3 小时）

1. 实现 `TextWrapper` 类
   - 基于 Token 列表构建行
   - 处理手动换行符 `\n`
   - 处理制表符 `\t`
   - 行宽度计算

2. 换行规则实现
   - 词边界断点
   - 标点断点规则
   - 禁止断点规则

3. 换行模块单元测试

### Phase 4：样式功能（1-2 小时）

1. 实现描边效果（多层绘制）
2. 实现行距控制
3. 实现对齐方式（左/中/右/上/中/下）
4. 实现边距控制

### Phase 5：高级功能（1-2 小时）

1. 实现自动高度计算
2. 实现字号自动缩放
3. 实现 Emoji 渲染支持
4. 性能优化（缓存机制）

### Phase 6：集成测试（1-2 小时）

1. 修改 `VideoUtils.py` 的 `edit_game_text_clip`
2. 修改 `VideoUtils.py` 的 `create_info_segment`（如有需要）
3. 端到端测试
4. 生成测试视频对比效果
5. 文档更新

---

## 8. 测试计划

### 8.1 单元测试

#### 8.1.1 分词测试

| 测试项 | 测试内容 | 输入 | 期望输出 |
|--------|----------|------|----------|
| `test_tokenize_chinese_basic` | 中文基础分词 | "大家好" | ["大家", "好"] |
| `test_tokenize_chinese_custom_dict` | 自定义词典 | "舞萌DX很好玩" | ["舞萌DX", "很", "好玩"] |
| `test_tokenize_english` | 英文分词 | "Hello World" | ["Hello", " ", "World"] |
| `test_tokenize_japanese` | 日文分词 | "こんにちは世界" | ["こん", "にち", "は", "世界"] |
| `test_tokenize_mixed` | 混合文本 | "Hello世界" | ["Hello", "世界"] |
| `test_tokenize_emoji` | Emoji 识别 | "你好😊世界" | ["你好", "😊", "世界"] |
| `test_tokenize_number` | 数字整体 | "得分12345分" | ["得分", "12345", "分"] |

#### 8.1.2 换行测试

| 测试项 | 测试内容 | 说明 |
|--------|----------|------|
| `test_wrap_chinese_word_boundary` | 中文按词边界换行 | "大家好" 不能断成 "大/家好" |
| `test_wrap_english_word_boundary` | 英文按空格换行 | "Hello World" 不能断成 "Hel/lo World" |
| `test_wrap_newline_preserve` | 保留手动换行 | "\n" 产生新行 |
| `test_wrap_tab_preserve` | 保留制表符 | "\t" 保留 |
| `test_wrap_punctuation_rule` | 标点断行规则 | 标点后可断，标点前不可断 |
| `test_wrap_mixed_text` | 混合文本换行 | 中英日混合正确换行 |
| `test_wrap_empty_text` | 空文本处理 | 返回空列表 |

#### 8.1.3 渲染测试

| 测试项 | 测试内容 |
|--------|----------|
| `test_render_basic` | 基础渲染 |
| `test_render_stroke` | 描边效果 |
| `test_render_alignment` | 对齐方式 |
| `test_render_emoji` | Emoji 渲染 |
| `test_auto_scale` | 自动缩放 |
| `test_save_to_file` | 保存为文件 |
| `test_transparent_background` | 透明背景 |

### 8.2 集成测试

1. 在 `edit_game_text_clip` 中使用新模块
2. 生成测试视频片段
3. 对比新旧方案输出效果

### 8.3 测试用例

```python
# 测试数据
TEST_CASES = [
    # 纯英文
    {
        "text": "This is a long English sentence that should be wrapped properly.",
        "expected_behavior": "按空格分词，在词边界换行"
    },

    # 纯中文 - 测试词语边界
    {
        "text": "大家好，欢迎来到舞萌DX的世界",
        "expected_tokens": ["大家", "好", "，", "欢迎", "来到", "舞萌DX", "的", "世界"],
        "expected_behavior": "在'大家'和'好'之间可换行，不在'大'和'家'之间换行"
    },

    # 纯日文
    {
        "text": "これは日本語のテキストです。正しく改行される必要があります。",
        "expected_behavior": "按字符或标点换行"
    },

    # 混合文本
    {
        "text": "Hello世界！This is 混合文本 with 日本語も入ってる。",
        "expected_behavior": "中英日分别按各自规则分词换行"
    },

    # 带换行符
    {
        "text": "第一行\n第二行\n第三行",
        "expected_lines": 3,
        "expected_behavior": "保留手动换行"
    },

    # 带 Emoji
    {
        "text": "Hello 😊 World 🌍 This is a test 😀",
        "expected_behavior": "Emoji 作为整体，不拆分"
    },

    # 数字整体
    {
        "text": "你的得分是123456分，排名第7名",
        "expected_behavior": "123456 和 7 不被拆分"
    },

    # 超长文本（测试自动缩放）
    {
        "text": "这是一段非常非常长的文本..." * 20,
        "expected_behavior": "自动缩小字号以适应容器"
    },

    # 边界情况
    {
        "text": "",
        "expected_behavior": "返回空结果"
    },
    {
        "text": "   ",
        "expected_behavior": "只包含空格时正确处理"
    },
    {
        "text": "\n\n\n",
        "expected_behavior": "多个换行符产生多个空行"
    },
]
```

### 8.4 视觉测试

生成测试图片，人工检查：

```python
# 生成测试图片的脚本
test_cases = [
    ("中文分词测试", "大家好欢迎来到这里玩舞萌DX游戏"),
    ("英文测试", "This is a test for English text wrapping"),
    ("日文测试", "こんにちは世界今日は良い天気ですね"),
    ("混合测试", "Hello世界！欢迎玩舞萌DX😊"),
    ("长文本测试", "这是一段很长的文本..." * 10),
]

for name, text in test_cases:
    renderer = TextRenderer(style, layout)
    img = renderer.render(text)
    img.save(f"test_output/{name}.png")
```

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Emoji 渲染不完美 | 部分设备 emoji 显示异常 | 提供多种字体 fallback |
| 性能问题 | 大量文字渲染耗时 | 缓存机制、延迟初始化 jieba |
| 字体缺失 | 渲染失败 | 提供默认字体 fallback |
| 兼容性 | 旧代码调用出错 | 保持接口兼容 |
| **分词准确性** | 中文分词可能不准确 | 自定义词典 + 后期优化 |
| **jieba 首次加载慢** | 词典加载耗时约 1-2 秒 | 模块级初始化，只加载一次 |
| **日文分词效果一般** | 字符级分词可能断在不自然位置 | 可选安装 tinysegmenter |

---

## 10. 验收标准

- [ ] 所有单元测试通过
- [ ] 集成测试视频输出正常
- [ ] 中英日文换行正确
- [ ] Emoji 正常显示
- [ ] 描边效果清晰
- [ ] 自动缩放功能正常
- [ ] 代码通过 review
- [ ] 文档更新完成

---

## 11. 时间估算

| 阶段 | 预估时间 |
|------|----------|
| Phase 1: 基础框架 | 2-3 小时 |
| Phase 2: 分词模块 | 3-4 小时 |
| Phase 3: 智能换行 | 2-3 小时 |
| Phase 4: 样式功能 | 1-2 小时 |
| Phase 5: 高级功能 | 1-2 小时 |
| Phase 6: 集成测试 | 1-2 小时 |
| **总计** | **10-16 小时** |

---

## 12. 参考资料

- [Pillow 官方文档 - ImageDraw](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html)
- [Pillow 文字绘制教程](https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html)
- [Unicode 字符范围参考](https://unicode-table.com/en/blocks/)
- [MoviePy ImageClip 文档](https://zulko.github.io/moviepy/ref/VideoClip/VideoClip.html#imageclip)
- [jieba 中文分词](https://github.com/fxsjy/jieba) - GitHub 33k+ stars
- [tinysegmenter](https://github.com/burgess17/tinysegmenter) - 轻量日文分词
- [CSS Text Wrapping](https://drafts.csswg.org/css-text-3/#line-breaking) - 断行规则参考

---

*文档结束*
