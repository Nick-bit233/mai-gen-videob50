"""
TextRenderer - 文字渲染模块
将文字渲染为透明 PNG 图片，支持多语言智能换行、描边、Emoji 等功能

Author: nanobot
Date: 2026-03-02
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Union
from PIL import Image, ImageDraw, ImageFont
import os
import re
import unicodedata
import numpy as np


# ============================================================================
# TextTokenizer - 智能分词器
# ============================================================================

class TextTokenizer:
    """
    智能分词器 - 支持中英日多语言分词
    
    使用示例:
        tokenizer = TextTokenizer()
        tokens = tokenizer.tokenize("大家好，欢迎来到这里")
        # ['大家', '好', '，', '欢迎', '来到', '这里']
    """
    
    # Unicode 范围定义
    CJK_RANGES = [
        (0x4E00, 0x9FFF),    # CJK 统一汉字
        (0x3400, 0x4DBF),    # CJK 扩展 A
        (0x20000, 0x2A6DF),  # CJK 扩展 B
        (0x2A700, 0x2B73F),  # CJK 扩展 C
        (0x2B740, 0x2B81F),  # CJK 扩展 D
        (0x2B820, 0x2CEAF),  # CJK 扩展 E
        (0xF900, 0xFAFF),    # CJK 兼容汉字
    ]
    
    HIRAGANA_RANGE = (0x3040, 0x309F)   # 平假名
    KATAKANA_RANGE = (0x30A0, 0x30FF)   # 片假名
    
    # 中文标点
    CHINESE_PUNCTUATION = "，。！？；：、""''（）【】《》…—"
    # 日文标点
    JAPANESE_PUNCTUATION = "、。！？「」『』（）【】…・"
    # 英文标点
    ENGLISH_PUNCTUATION = ",.!?;:'\"()[]{}<>-"
    
    _jieba_initialized = False
    
    def __init__(self, custom_dict_path: Optional[str] = None):
        """
        初始化分词器
        
        Args:
            custom_dict_path: 自定义词典路径（可选）
        """
        self._init_jieba(custom_dict_path)
    
    def _init_jieba(self, custom_dict_path: Optional[str] = None) -> None:
        """初始化 jieba 分词器"""
        if TextTokenizer._jieba_initialized:
            return
        
        try:
            import jieba
            
            # 加载自定义词典
            if custom_dict_path and os.path.exists(custom_dict_path):
                jieba.load_userdict(custom_dict_path)
            
            # 添加音游相关词汇
            gaming_words = [
                ("舞萌DX", 5, "n"),
                ("中二节奏", 5, "n"),
                ("谱面确认", 5, "n"),
                ("分表", 5, "n"),
                ("B50", 5, "n"),
                ("B30", 5, "n"),
                ("DX Rating", 5, "n"),
                ("AP", 5, "n"),
                ("FC", 5, "n"),
                ("全连", 5, "v"),
                ("收歌", 5, "v"),
                ("推分", 5, "v"),
                ("SSS", 5, "n"),
                ("SSSplus", 5, "n"),
            ]
            
            for word, freq, tag in gaming_words:
                jieba.add_word(word, freq, tag)
            
            TextTokenizer._jieba_initialized = True
            
        except ImportError:
            # jieba 未安装，将使用字符级分词
            pass
    
    def tokenize(self, text: str) -> List[str]:
        """
        对文本进行分词
        
        Args:
            text: 输入文本
            
        Returns:
            分词结果列表
        """
        if not text:
            return []
        
        # 检测是否包含中文/日文
        has_cjk = any(self._is_chinese(c) or self._is_japanese(c) for c in text)
        
        if has_cjk:
            # 包含 CJK 字符，使用 jieba 进行整体分词
            return self._tokenize_with_jieba(text)
        else:
            # 纯 ASCII 文本，按空格分词
            return self._tokenize_ascii(text)
    
    def _tokenize_with_jieba(self, text: str) -> List[str]:
        """
        使用 jieba 对文本进行分词（处理混合文本）
        
        Args:
            text: 输入文本
            
        Returns:
            分词结果列表
        """
        try:
            import jieba
            # jieba 可以处理中英混合文本
            raw_tokens = list(jieba.cut(text))
            
            # 后处理：分离标点和换行符
            tokens = []
            for token in raw_tokens:
                if not token:
                    continue
                
                # 检查是否包含换行符
                if '\n' in token:
                    # 分割换行符
                    parts = token.split('\n')
                    for i, part in enumerate(parts):
                        if part:
                            tokens.append(part)
                        if i < len(parts) - 1:
                            tokens.append('\n')
                # 检查是否是标点
                elif len(token) == 1 and self._is_punctuation(token):
                    tokens.append(token)
                # 检查是否是空格
                elif token == ' ' or token == '\t':
                    tokens.append(token)
                else:
                    tokens.append(token)
            
            return tokens
            
        except ImportError:
            # jieba 未安装，回退到字符级分词
            return self._tokenize_by_char(text)
    
    def _tokenize_ascii(self, text: str) -> List[str]:
        """
        对纯 ASCII 文本进行分词
        
        Args:
            text: 输入文本
            
        Returns:
            分词结果列表
        """
        tokens = []
        i = 0
        
        while i < len(text):
            char = text[i]
            
            # 换行符
            if char == '\n':
                tokens.append('\n')
                i += 1
            # 空格和制表符
            elif char in ' \t':
                tokens.append(char)
                i += 1
            # 标点符号
            elif self._is_punctuation(char):
                tokens.append(char)
                i += 1
            # ASCII 单词
            else:
                word, length = self._extract_ascii_word(text, i)
                tokens.append(word)
                i += length
        
        return tokens
    
    def _tokenize_by_char(self, text: str) -> List[str]:
        """
        字符级分词（回退方案）
        
        Args:
            text: 输入文本
            
        Returns:
            分词结果列表
        """
        tokens = []
        for char in text:
            if char == '\n':
                tokens.append('\n')
            elif char in ' \t':
                tokens.append(char)
            else:
                tokens.append(char)
        return tokens
    
    def _is_chinese(self, char: str) -> bool:
        """判断是否为中文字符"""
        if len(char) != 1:
            return False
        code = ord(char)
        for start, end in self.CJK_RANGES:
            if start <= code <= end:
                return True
        return False
    
    def _is_japanese(self, char: str) -> bool:
        """判断是否为日文字符（平假名/片假名）"""
        if len(char) != 1:
            return False
        code = ord(char)
        return (self.HIRAGANA_RANGE[0] <= code <= self.HIRAGANA_RANGE[1] or
                self.KATAKANA_RANGE[0] <= code <= self.KATAKANA_RANGE[1])
    
    def _is_korean(self, char: str) -> bool:
        """判断是否为韩文字符"""
        if len(char) != 1:
            return False
        code = ord(char)
        return 0xAC00 <= code <= 0xD7AF
    
    def _is_emoji(self, char: str) -> bool:
        """判断是否为 Emoji"""
        if len(char) != 1:
            return False
        # 使用 Unicode 属性判断
        try:
            name = unicodedata.name(char, '')
            return 'EMOJI' in name or 'EMOTICON' in name
        except ValueError:
            return False
        
        # 简单范围检查（常见 Emoji 范围）
        code = ord(char)
        emoji_ranges = [
            (0x1F600, 0x1F64F),  # Emoticons
            (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
            (0x1F680, 0x1F6FF),  # Transport and Map
            (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
            (0x2600, 0x26FF),    # Misc symbols
            (0x2700, 0x27BF),    # Dingbats
        ]
        
        for start, end in emoji_ranges:
            if start <= code <= end:
                return True
        return False
    
    def _is_punctuation(self, char: str) -> bool:
        """判断是否为标点符号"""
        return (char in self.CHINESE_PUNCTUATION or 
                char in self.JAPANESE_PUNCTUATION or 
                char in self.ENGLISH_PUNCTUATION)
    
    def _extract_emoji(self, text: str, start: int) -> Tuple[str, int]:
        """提取 Emoji（可能包含多个 Unicode 码点）"""
        # 简单实现：返回单个字符
        # 复杂的 Emoji（如带修饰符的）需要更复杂的处理
        return text[start], 1
    
    def _extract_chinese(self, text: str, start: int) -> Tuple[str, int]:
        """提取连续的中文字符"""
        end = start
        while end < len(text) and self._is_chinese(text[end]):
            end += 1
        return text[start:end], end - start
    
    def _extract_japanese(self, text: str, start: int) -> Tuple[str, int]:
        """提取连续的日文字符"""
        end = start
        while end < len(text) and (self._is_japanese(text[end]) or self._is_chinese(text[end])):
            # 日文文本可能包含汉字，一起提取
            end += 1
        return text[start:end], end - start
    
    def _extract_korean(self, text: str, start: int) -> Tuple[str, int]:
        """提取连续的韩文字符"""
        end = start
        while end < len(text) and self._is_korean(text[end]):
            end += 1
        return text[start:end], end - start
    
    def _extract_ascii_word(self, text: str, start: int) -> Tuple[str, int]:
        """提取 ASCII 单词（包括数字）"""
        end = start
        while end < len(text) and text[end].isascii() and not text[end].isspace() and not self._is_punctuation(text[end]):
            end += 1
        return text[start:end], end - start
    
    def _tokenize_chinese(self, text: str) -> List[str]:
        """对中文文本进行分词"""
        try:
            import jieba
            return list(jieba.cut(text))
        except ImportError:
            # jieba 未安装，按字符分
            return list(text)
    
    def _tokenize_japanese(self, text: str) -> List[str]:
        """对日文文本进行分词"""
        # 简单实现：字符级 + 标点断点
        result = []
        current = ""
        
        for char in text:
            if self._is_punctuation(char):
                if current:
                    result.append(current)
                    current = ""
                result.append(char)
            else:
                current += char
        
        if current:
            result.append(current)
        
        return result


@dataclass
class TextStyle:
    """文字样式配置"""
    font_path: str                         # 字体文件路径
    font_size: int = 24                    # 字号
    color: str = "#FFFFFF"                 # 文字颜色 (十六进制)
    stroke_color: Optional[str] = None     # 描边颜色 (None 表示无描边)
    stroke_width: int = 2                  # 描边宽度 (像素)
    emoji_font_path: Optional[str] = None  # Emoji 字体文件路径 (None 表示不单独处理 emoji)

    def __post_init__(self):
        """验证样式参数"""
        if self.font_size <= 0:
            raise ValueError(f"font_size must be positive, got {self.font_size}")
        if self.stroke_width < 0:
            raise ValueError(f"stroke_width must be non-negative, got {self.stroke_width}")


@dataclass
class LayoutConfig:
    """布局配置"""
    width: int = 800                       # 图片宽度
    height: int = 600                      # 图片高度 (auto_height=True 时忽略)
    auto_height: bool = True               # 自动计算高度
    padding: Tuple[int, int, int, int] = (20, 20, 20, 20)  # 上右下左边距
    line_spacing: int = 8                  # 行距 (像素)
    horizontal_align: str = "left"         # 水平对齐: left/center/right
    vertical_align: str = "top"            # 垂直对齐: top/center/bottom
    max_lines: Optional[int] = None        # 最大行数 (None 表示无限制)

    def __post_init__(self):
        """验证布局参数"""
        valid_h_align = ("left", "center", "right")
        valid_v_align = ("top", "center", "bottom")
        
        if self.horizontal_align not in valid_h_align:
            raise ValueError(f"horizontal_align must be one of {valid_h_align}, got '{self.horizontal_align}'")
        if self.vertical_align not in valid_v_align:
            raise ValueError(f"vertical_align must be one of {valid_v_align}, got '{self.vertical_align}'")
        if self.width <= 0:
            raise ValueError(f"width must be positive, got {self.width}")
        if self.height <= 0 and not self.auto_height:
            raise ValueError(f"height must be positive when auto_height=False, got {self.height}")


class TextRenderer:
    """
    文字渲染器 - 将文字渲染为透明 PNG 图片
    
    使用示例:
        style = TextStyle(font_path="path/to/font.ttf", font_size=32, color="#FFFFFF")
        layout = LayoutConfig(width=800, auto_height=True)
        renderer = TextRenderer(style, layout)
        
        # 渲染为 PIL Image
        image = renderer.render("Hello 世界")
        
        # 渲染并保存为文件
        renderer.render_to_file("Hello 世界", "output.png")
    """
    
    # 类级别的分词器实例（延迟初始化）
    _tokenizer: Optional[TextTokenizer] = None
    
    # 默认 Emoji 字体路径（相对路径）
    DEFAULT_EMOJI_FONT = "static/assets/fonts/NotoColorEmoji.ttf"
    
    def __init__(self, style: TextStyle, layout: LayoutConfig):
        """
        初始化渲染器
        
        Args:
            style: 文字样式配置
            layout: 布局配置
        """
        self.style = style
        self.layout = layout
        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._emoji_font: Optional[ImageFont.FreeTypeFont] = None
        self._original_font_size = style.font_size  # 保存原始字号用于自动缩放
        
        # 初始化分词器
        if TextRenderer._tokenizer is None:
            TextRenderer._tokenizer = TextTokenizer()
    
    @classmethod
    def set_custom_dict(cls, dict_path: str) -> None:
        """设置自定义词典路径"""
        cls._tokenizer = TextTokenizer(dict_path)
    
    @property
    def font(self) -> ImageFont.FreeTypeFont:
        """延迟加载字体"""
        if self._font is None:
            self._load_font()
        return self._font
    
    def _load_font(self, size: Optional[int] = None) -> None:
        """
        加载字体文件
        
        Args:
            size: 字体大小，None 时使用 style.font_size
        """
        font_size = size if size is not None else self.style.font_size
        
        if not os.path.exists(self.style.font_path):
            raise FileNotFoundError(f"Font file not found: {self.style.font_path}")
        
        try:
            self._font = ImageFont.truetype(self.style.font_path, font_size)
            self.style.font_size = font_size
        except Exception as e:
            raise RuntimeError(f"Failed to load font '{self.style.font_path}': {e}")
    
    def _load_emoji_font(self, size: Optional[int] = None) -> None:
        """
        加载 Emoji 字体文件
        
        Args:
            size: 字体大小，None 时使用 style.font_size
        """
        font_size = size if size is not None else self.style.font_size
        
        # 确定 emoji 字体路径
        emoji_font_path = self.style.emoji_font_path
        if emoji_font_path is None:
            # 使用默认 emoji 字体
            emoji_font_path = self.DEFAULT_EMOJI_FONT
        
        if not os.path.exists(emoji_font_path):
            # Emoji 字体不存在，将不单独处理 emoji
            self._emoji_font = None
            return
        
        try:
            # Noto Color Emoji 的字号需要调整以匹配主字体
            # 因为它是位图字体，需要用更大的字号才能达到相同的视觉大小
            self._emoji_font = ImageFont.truetype(emoji_font_path, font_size)
        except Exception as e:
            # 加载失败，不单独处理 emoji
            self._emoji_font = None
    
    @property
    def emoji_font(self) -> Optional[ImageFont.FreeTypeFont]:
        """延迟加载 emoji 字体"""
        if self._emoji_font is None and (self.style.emoji_font_path or os.path.exists(self.DEFAULT_EMOJI_FONT)):
            self._load_emoji_font()
        return self._emoji_font
    
    def _render_emoji_with_freetype(self, emoji_char: str, font_size: int) -> Optional[Image.Image]:
        """
        使用 freetype-py 渲染 emoji 到 PIL Image
        
        Args:
            emoji_char: emoji 字符
            font_size: 字体大小
            
        Returns:
            PIL Image 对象，如果失败返回 None
        """
        try:
            import freetype
            
            # 确定 emoji 字体路径
            emoji_font_path = self.style.emoji_font_path
            if emoji_font_path is None:
                emoji_font_path = self.DEFAULT_EMOJI_FONT
            
            if not os.path.exists(emoji_font_path):
                return None
            
            # 加载字体
            face = freetype.Face(emoji_font_path)
            face.set_pixel_sizes(0, font_size)
            
            # 获取 emoji 的 Unicode 码点
            char_code = ord(emoji_char[0])
            
            # 获取字形索引
            glyph_index = face.get_char_index(char_code)
            if glyph_index == 0:
                # 尝试使用字符本身
                return None
            
            # 加载字形（使用 RENDER 标志来获取位图）
            face.load_glyph(glyph_index, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_COLOR)
            
            # 获取字形位图
            bitmap = face.glyph.bitmap
            if bitmap.width == 0 or bitmap.rows == 0:
                return None
            
            # 将位图数据转换为 numpy 数组
            if bitmap.pixel_mode == freetype.FT_PIXEL_MODE_BGRA:
                # BGRA 模式（彩色 emoji）
                buffer = np.array(bitmap.buffer, dtype=np.uint8)
                buffer = buffer.reshape((bitmap.rows, bitmap.width, 4))
                # BGRA -> RGBA
                buffer = buffer[:, :, [2, 1, 0, 3]]
                img = Image.fromarray(buffer, 'RGBA')
            else:
                # 灰度模式
                buffer = np.array(bitmap.buffer, dtype=np.uint8)
                buffer = buffer.reshape((bitmap.rows, bitmap.width))
                img = Image.fromarray(buffer, 'L')
                # 转换为 RGBA
                img = img.convert('RGBA')
                # 将灰度值作为 alpha 通道
                r, g, b, a = img.split()
                img = Image.merge('RGBA', (r, g, b, a))
            
            return img
            
        except Exception as e:
            return None
    
    def _set_font_size(self, size: int) -> None:
        """设置字体大小（重新加载字体）"""
        self._load_font(size)
        # 同时更新 emoji 字体大小
        if self._emoji_font is not None:
            self._load_emoji_font(size)
    
    @staticmethod
    def _is_emoji_char(char: str) -> bool:
        """
        判断是否为 Emoji 字符
        
        Args:
            char: 单个字符或 Unicode 字符
            
        Returns:
            是否为 Emoji
        """
        if not char:
            return False
        
        code = ord(char[0])
        
        # Emoji Unicode 范围
        emoji_ranges = [
            (0x1F600, 0x1F64F),  # Emoticons (😀-🙏)
            (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs (🌀-🗿)
            (0x1F680, 0x1F6FF),  # Transport and Map (🚀-🛿)
            (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs (🤀-🧿)
            (0x1FA00, 0x1FA6F),  # Chess Symbols
            (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
            (0x2600, 0x26FF),    # Misc symbols (☀-⛿)
            (0x2700, 0x27BF),    # Dingbats (✀-➿)
            (0xFE00, 0xFE0F),    # Variation Selectors
            (0x1F000, 0x1F02F),  # Mahjong Tiles
            (0x1F0A0, 0x1F0FF),  # Playing Cards
            (0x231A, 0x231B),    # Watch, Hourglass
            (0x23E9, 0x23F3),    # Various symbols
            (0x23F8, 0x23FA),    # Media control
            (0x25AA, 0x25AB),    # Squares
            (0x25B6, 0x25B6),    # Play button
            (0x25C0, 0x25C0),    # Reverse button
            (0x25FB, 0x25FE),    # Squares
            (0x2614, 0x2615),    # Umbrella, Hot beverage
            (0x2648, 0x2653),    # Zodiac
            (0x267F, 0x267F),    # Wheelchair
            (0x2693, 0x2693),    # Anchor
            (0x26A1, 0x26A1),    # High voltage
            (0x26AA, 0x26AB),    # Circles
            (0x26BD, 0x26BE),    # Soccer, Baseball
            (0x26C4, 0x26C5),    # Snowman, Sun
            (0x26CE, 0x26CE),    # Ophiuchus
            (0x26D4, 0x26D4),    # No entry
            (0x26EA, 0x26EA),    # Church
            (0x26F2, 0x26F3),    # Fountain, Golf
            (0x26F5, 0x26F5),    # Sailboat
            (0x26FA, 0x26FA),    # Tent
            (0x26FD, 0x26FD),    # Fuel pump
            (0x2702, 0x2702),    # Scissors
            (0x2705, 0x2705),    # Check mark
            (0x2708, 0x270D),    # Various
            (0x270F, 0x270F),    # Pencil
            (0x2712, 0x2712),    # Black nib
            (0x2714, 0x2714),    # Heavy check mark
            (0x2716, 0x2716),    # Heavy multiplication
            (0x271D, 0x271D),    # Latin cross
            (0x2721, 0x2721),    # Star of David
            (0x2728, 0x2728),    # Sparkles
            (0x2733, 0x2734),    # Eight spoked asterisk
            (0x2744, 0x2744),    # Snowflake
            (0x2747, 0x2747),    # Sparkle
            (0x274C, 0x274C),    # Cross mark
            (0x274E, 0x274E),    # Cross mark
            (0x2753, 0x2755),    # Question marks
            (0x2757, 0x2757),    # Exclamation mark
            (0x2763, 0x2764),    # Heart exclamation, Heavy heart
            (0x2795, 0x2797),    # Plus, minus, divide
            (0x27A1, 0x27A1),    # Black right arrow
            (0x27B0, 0x27B0),    # Curly loop
            (0x27BF, 0x27BF),    # Double curly loop
            (0x2934, 0x2935),    # Arrows
            (0x2B05, 0x2B07),    # Arrows
            (0x2B1B, 0x2B1C),    # Squares
            (0x2B50, 0x2B50),    # Star
            (0x2B55, 0x2B55),    # Heavy large circle
            (0x3030, 0x3030),    # Wavy dash
            (0x303D, 0x303D),    # Part alternation mark
            (0x3297, 0x3297),    # Circled ideograph congratulation
            (0x3299, 0x3299),    # Circled ideograph secret
            (0x200D, 0x200D),    # Zero Width Joiner (用于组合 emoji)
            (0x20E3, 0x20E3),    # Combining Enclosing Keycap
            (0x00A9, 0x00A9),    # Copyright
            (0x00AE, 0x00AE),    # Registered
            (0x2122, 0x2122),    # Trade Mark
            (0x2139, 0x2139),    # Information Source
            (0x2194, 0x2199),    # Arrows
            (0x21A9, 0x21AA),    # Arrows
            (0x1F004, 0x1F004),  # Mahjong Red Dragon
            (0x1F0CF, 0x1F0CF),  # Playing Card Joker
        ]
        
        for start, end in emoji_ranges:
            if start <= code <= end:
                return True
        
        # 检查是否包含 Emoji 修饰符
        if 0x1F3FB <= code <= 0x1F3FF:  # Skin tone modifiers
            return True
        
        # 检查是否为 Regional Indicator (国旗)
        if 0x1F1E6 <= code <= 0x1F1FF:
            return True
        
        return False
    
    def _segment_text_by_emoji(self, text: str) -> List[Tuple[str, bool]]:
        """
        将文本按 Emoji 分段
        
        Args:
            text: 输入文本
            
        Returns:
            分段列表，每个元素为 (片段文本, 是否为 emoji)
        """
        if not text:
            return []
        
        if self.emoji_font is None:
            # 没有 emoji 字体，不进行分段
            return [(text, False)]
        
        segments = []
        i = 0
        
        while i < len(text):
            char = text[i]
            
            # 检查是否是 emoji
            if self._is_emoji_char(char):
                # 收集完整的 emoji（可能包含修饰符）
                emoji_start = i
                i += 1
                
                # 处理 emoji 序列（如国旗、带肤色修饰符的 emoji）
                while i < len(text):
                    next_char = text[i]
                    next_code = ord(next_char)
                    
                    # Zero Width Joiner - 继续收集
                    if next_code == 0x200D:
                        i += 1
                        if i < len(text):
                            i += 1  # 收集 ZWJ 后的字符
                        continue
                    
                    # Variation Selector - 继续收集
                    if 0xFE00 <= next_code <= 0xFE0F:
                        i += 1
                        continue
                    
                    # Skin tone modifier - 继续收集
                    if 0x1F3FB <= next_code <= 0x1F3FF:
                        i += 1
                        continue
                    
                    # Regional Indicator (国旗的第二部分)
                    if 0x1F1E6 <= next_code <= 0x1F1FF and i - emoji_start == 1:
                        i += 1
                        continue
                    
                    break
                
                segments.append((text[emoji_start:i], True))
            else:
                # 收集非 emoji 字符
                text_start = i
                while i < len(text) and not self._is_emoji_char(text[i]):
                    i += 1
                segments.append((text[text_start:i], False))
        
        return segments
    
    def render(self, text: str, auto_scale: bool = True) -> Image.Image:
        """
        渲染文字为 PIL Image 对象（支持 Emoji 混排）
        
        Args:
            text: 要渲染的文字
            auto_scale: 当文字超出容器时是否自动缩放字号
            
        Returns:
            PIL Image 对象 (RGBA 模式，透明背景)
        """
        if not text:
            # 空文本返回透明图片
            return Image.new("RGBA", (self.layout.width, 1), (0, 0, 0, 0))
        
        # 检查是否有 emoji 字体可用
        has_emoji_font = self.emoji_font is not None
        
        # 分词和换行处理
        if has_emoji_font:
            lines = self._wrap_text_with_emoji(text)
        else:
            lines = self._wrap_text(text)
        
        # 检查是否需要自动缩放
        if auto_scale and self._needs_scaling(lines):
            self._auto_scale_font(text)
            # 重新计算换行
            if has_emoji_font:
                lines = self._wrap_text_with_emoji(text)
            else:
                lines = self._wrap_text(text)
        
        # 计算所需高度
        content_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        line_heights = []
        line_widths = []
        
        for line in lines:
            if isinstance(line, list):
                # 带 emoji 分段的行
                line_width, line_height = self._measure_segmented_line(line)
            else:
                # 纯文本行
                bbox = self.font.getbbox(line)
                line_width = bbox[2] - bbox[0]
                line_height = bbox[3] - bbox[1]
            line_widths.append(line_width)
            line_heights.append(line_height)
        
        total_text_height = sum(line_heights) + self.layout.line_spacing * (len(lines) - 1)
        
        # 计算最终图片高度
        if self.layout.auto_height:
            image_height = total_text_height + self.layout.padding[0] + self.layout.padding[2]
        else:
            image_height = self.layout.height
        
        # 创建透明图片
        image = Image.new("RGBA", (self.layout.width, image_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 计算起始 Y 坐标（垂直对齐）
        if self.layout.vertical_align == "top":
            current_y = self.layout.padding[0]
        elif self.layout.vertical_align == "center":
            current_y = self.layout.padding[0] + (image_height - self.layout.padding[0] - self.layout.padding[2] - total_text_height) // 2
        else:  # bottom
            current_y = image_height - self.layout.padding[2] - total_text_height
        
        # 绘制每一行
        for i, line in enumerate(lines):
            line_height = line_heights[i]
            line_width = line_widths[i]
            
            # 计算水平位置
            if self.layout.horizontal_align == "left":
                x = self.layout.padding[3]
            elif self.layout.horizontal_align == "center":
                x = self.layout.padding[3] + (content_width - line_width) // 2
            else:  # right
                x = self.layout.width - self.layout.padding[1] - line_width
            
            y = current_y
            
            # 绘制该行
            if isinstance(line, list):
                # 带 emoji 分段的行 - 分段绘制
                self._draw_segmented_line(draw, line, x, y, line_height, image)
            else:
                # 纯文本行 - 直接绘制
                # 绘制描边（如果启用）
                if self.style.stroke_color and self.style.stroke_width > 0:
                    self._draw_stroke(draw, line, x, y, self.font, self.style.stroke_color, self.style.stroke_width)
                # 绘制文字
                draw.text((x, y), line, font=self.font, fill=self._parse_color(self.style.color))
            
            current_y += line_height + self.layout.line_spacing
        
        return image
    
    def _measure_segmented_line(self, segments: List[Tuple[str, bool]]) -> Tuple[int, int]:
        """
        测量带 emoji 分段的行的尺寸
        
        Args:
            segments: 分段列表 [(文本, 是否emoji), ...]
            
        Returns:
            (总宽度, 最大高度)
        """
        total_width = 0
        max_height = 0
        
        for text, is_emoji in segments:
            if is_emoji and self.emoji_font:
                bbox = self.emoji_font.getbbox(text)
            else:
                bbox = self.font.getbbox(text)
            total_width += bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            max_height = max(max_height, height)
        
        return total_width, max_height
    
    def _draw_segmented_line(self, draw: ImageDraw.ImageDraw, segments: List[Tuple[str, bool]], 
                             x: float, y: float, line_height: int, base_image: Image.Image) -> None:
        """
        绘制带 emoji 分段的行
        
        Args:
            draw: ImageDraw 对象
            segments: 分段列表 [(文本, 是否emoji), ...]
            x: 起始 X 坐标
            y: 起始 Y 坐标
            line_height: 行高度（用于垂直对齐）
            base_image: 基础图片（用于合成 emoji）
        """
        current_x = x
        
        for text, is_emoji in segments:
            if is_emoji:
                # 使用 freetype-py 渲染 emoji
                emoji_img = self._render_emoji_with_freetype(text, self.style.font_size)
                
                if emoji_img:
                    # 计算 emoji 尺寸
                    emoji_width, emoji_height = emoji_img.size
                    
                    # 垂直居中对齐
                    segment_y = y + (line_height - emoji_height) // 2
                    
                    # 将 emoji 图片粘贴到基础图片上
                    if emoji_img.mode == 'RGBA':
                        base_image.paste(emoji_img, (int(current_x), int(segment_y)), emoji_img)
                    else:
                        base_image.paste(emoji_img, (int(current_x), int(segment_y)))
                    
                    current_x += emoji_width
                else:
                    # freetype 渲染失败，尝试使用 PIL 默认方式
                    bbox = self.font.getbbox(text)
                    segment_height = bbox[3] - bbox[1]
                    segment_y = y + (line_height - segment_height) // 2
                    draw.text((current_x, segment_y), text, font=self.font, 
                             fill=self._parse_color(self.style.color))
                    current_x += bbox[2] - bbox[0]
            else:
                # 普通文字
                bbox = self.font.getbbox(text)
                segment_height = bbox[3] - bbox[1]
                # 垂直居中对齐
                segment_y = y + (line_height - segment_height) // 2
                
                # 绘制描边（如果启用）
                if self.style.stroke_color and self.style.stroke_width > 0:
                    self._draw_stroke(draw, text, current_x, segment_y, self.font, 
                                     self.style.stroke_color, self.style.stroke_width)
                
                # 绘制文字
                draw.text((current_x, segment_y), text, font=self.font, 
                         fill=self._parse_color(self.style.color))
                current_x += bbox[2] - bbox[0]
    
    def _wrap_text_with_emoji(self, text: str) -> List:
        """
        智能换行处理（支持 Emoji 混排）
        
        Args:
            text: 原始文本
            
        Returns:
            换行后的行列表，每行是分段列表 [(文本, 是否emoji), ...]
        """
        max_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        
        # 首先按换行符分段
        paragraphs = text.split('\n')
        
        all_lines = []
        
        for para in paragraphs:
            if not para:
                all_lines.append([])
                continue
            
            # 对每个段落进行 emoji 分段
            segments = self._segment_text_by_emoji(para)
            
            # 对分段后的文本进行词级别分词（只处理非 emoji 部分）
            tokenized_segments = []
            for seg_text, is_emoji in segments:
                if is_emoji:
                    tokenized_segments.append((seg_text, True))
                else:
                    # 对非 emoji 文本进行词级别分词
                    tokens = self._tokenizer.tokenize(seg_text)
                    for token in tokens:
                        tokenized_segments.append((token, False))
            
            # 构建行
            current_line = []
            current_line_width = 0
            
            for seg_text, is_emoji in tokenized_segments:
                # 获取该分段宽度
                if is_emoji and self.emoji_font:
                    bbox = self.emoji_font.getbbox(seg_text)
                else:
                    bbox = self.font.getbbox(seg_text)
                seg_width = bbox[2] - bbox[0]
                
                if current_line_width + seg_width <= max_width:
                    # 可以放入当前行
                    current_line.append((seg_text, is_emoji))
                    current_line_width += seg_width
                else:
                    # 放不下
                    if current_line:
                        # 输出当前行
                        all_lines.append(current_line)
                        current_line = [(seg_text, is_emoji)]
                        current_line_width = seg_width
                    else:
                        # 单个分段就放不下，强制放入（后续会触发自动缩放）
                        current_line.append((seg_text, is_emoji))
                        current_line_width = seg_width
            
            # 添加最后一行
            if current_line:
                all_lines.append(current_line)
        
        return all_lines if all_lines else [[]]
    
    def _needs_scaling(self, lines: List) -> bool:
        """
        检查是否需要缩放字号
        
        Args:
            lines: 当前行列表（可能是字符串列表或分段列表）
            
        Returns:
            是否需要缩放
        """
        # 检查行数是否超过限制
        if self.layout.max_lines and len(lines) > self.layout.max_lines:
            return True
        
        # 检查是否有固定高度限制且超出
        if not self.layout.auto_height:
            content_height = self.layout.height - self.layout.padding[0] - self.layout.padding[2]
            
            # 计算行高
            if lines and isinstance(lines[0], list):
                # 分段格式
                line_heights = []
                for line in lines:
                    if line:
                        _, h = self._measure_segmented_line(line)
                        line_heights.append(h)
                    else:
                        line_heights.append(self.font.getbbox("测试")[3])
                total_height = sum(line_heights) + self.layout.line_spacing * max(0, len(lines) - 1)
            else:
                # 字符串格式
                line_height = self.font.getbbox("测试")[3] - self.font.getbbox("测试")[1]
                total_height = len(lines) * line_height + self.layout.line_spacing * max(0, len(lines) - 1)
            
            if total_height > content_height:
                return True
        
        # 检查是否有行超出宽度
        max_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        for line in lines:
            if isinstance(line, list):
                line_width, _ = self._measure_segmented_line(line)
            else:
                bbox = self.font.getbbox(line)
                line_width = bbox[2] - bbox[0]
            
            if line_width > max_width:
                return True
        
        return False
    
    def _auto_scale_font(self, text: str) -> None:
        """
        自动缩放字号以适应容器
        
        Args:
            text: 原始文本
        """
        original_size = self._original_font_size
        min_size = max(8, original_size // 4)  # 最小字号为原始的 1/4 或 8px
        
        # 二分查找合适的字号
        low, high = min_size, original_size
        best_size = original_size
        
        while low <= high:
            mid = (low + high) // 2
            self._set_font_size(mid)
            lines = self._wrap_text(text)
            
            if self._fits_container(lines):
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1
        
        # 使用找到的最佳字号
        if best_size != self.style.font_size:
            self._set_font_size(best_size)
    
    def _fits_container(self, lines: List) -> bool:
        """
        检查行列表是否适合容器
        
        Args:
            lines: 行列表（可能是字符串列表或分段列表）
            
        Returns:
            是否适合容器
        """
        # 检查行数限制
        if self.layout.max_lines and len(lines) > self.layout.max_lines:
            return False
        
        # 检查高度限制
        if not self.layout.auto_height:
            content_height = self.layout.height - self.layout.padding[0] - self.layout.padding[2]
            
            # 计算总高度
            if lines and isinstance(lines[0], list):
                line_heights = []
                for line in lines:
                    if line:
                        _, h = self._measure_segmented_line(line)
                        line_heights.append(h)
                    else:
                        line_heights.append(self.font.getbbox("测试")[3])
                total_height = sum(line_heights) + self.layout.line_spacing * max(0, len(lines) - 1)
            else:
                line_height = self.font.getbbox("测试")[3] - self.font.getbbox("测试")[1]
                total_height = len(lines) * line_height + self.layout.line_spacing * max(0, len(lines) - 1)
            
            if total_height > content_height:
                return False
        
        # 检查宽度限制
        max_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        for line in lines:
            if isinstance(line, list):
                line_width, _ = self._measure_segmented_line(line)
            else:
                bbox = self.font.getbbox(line)
                line_width = bbox[2] - bbox[0]
            
            if line_width > max_width:
                return False
        
        return True
    
    def _draw_stroke(self, draw: ImageDraw.ImageDraw, text: str, x: float, y: float, 
                     font: ImageFont.FreeTypeFont, stroke_color: str, stroke_width: int) -> None:
        """
        绘制文字描边（通过多层绘制实现）
        
        Args:
            draw: PIL ImageDraw 对象
            text: 要绘制的文字
            x, y: 文字位置
            font: 字体对象
            stroke_color: 描边颜色
            stroke_width: 描边宽度
        """
        color = self._parse_color(stroke_color)
        
        # 8 方向绘制描边
        for angle in range(0, 360, 45):
            import math
            dx = stroke_width * math.cos(math.radians(angle))
            dy = stroke_width * math.sin(math.radians(angle))
            draw.text((x + dx, y + dy), text, font=font, fill=color)
    
    def _parse_color(self, color: str) -> Tuple[int, int, int, int]:
        """
        解析颜色字符串为 RGBA 元组
        
        Args:
            color: 颜色字符串，支持格式：
                   - "#RGB"
                   - "#RRGGBB"
                   - "#RRGGBBAA"
                   - "rgb(r, g, b)"
                   - "rgba(r, g, b, a)"
                   - 颜色名称 (如 "white", "black")
                   
        Returns:
            (r, g, b, a) 元组
        """
        from PIL import ImageColor
        
        try:
            parsed = ImageColor.getcolor(color, "RGBA")
            if parsed is None:
                # 默认白色
                return (255, 255, 255, 255)
            if len(parsed) == 3:
                return (*parsed, 255)
            return parsed
        except ValueError:
            # 解析失败，返回白色
            return (255, 255, 255, 255)
    
    def _wrap_text(self, text: str) -> List[str]:
        """
        智能换行处理
        
        Args:
            text: 原始文本
            
        Returns:
            换行后的行列表
        """
        max_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        
        # 使用分词器进行分词
        tokens = self._tokenizer.tokenize(text)
        
        # 构建行
        lines = []
        current_line = ""
        
        for token in tokens:
            # 手动换行符
            if token == '\n':
                lines.append(current_line)
                current_line = ""
                continue
            
            test_line = current_line + token
            bbox = self.font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                # 当前 token 放不下
                if current_line:
                    # 先输出当前行
                    lines.append(current_line)
                    current_line = token
                else:
                    # 即使是单个 token 也放不下，强制换行（按字符拆分）
                    # 这种情况通常是因为容器太窄或字号太大
                    for char in token:
                        test_line = current_line + char
                        bbox = self.font.getbbox(test_line)
                        width = bbox[2] - bbox[0]
                        
                        if width <= max_width:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = char
        
        # 添加最后一行
        if current_line:
            lines.append(current_line)
        
        # 过滤空行（保留至少一个空行用于显示）
        if not lines:
            return [""]
        
        return lines
    
    def _simple_wrap(self, text: str, max_width: int) -> List[str]:
        """
        简单换行（字符级）- 保留用于 fallback
        
        Args:
            text: 文本（不含手动换行符）
            max_width: 最大行宽
            
        Returns:
            行列表
        """
        if not text:
            return [""]
        
        lines = []
        current_line = ""
        
        for char in text:
            test_line = current_line + char
            bbox = self.font.getbbox(test_line)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [""]
    
    def render_to_file(self, text: str, output_path: str) -> str:
        """
        渲染文字并保存为 PNG 文件
        
        Args:
            text: 要渲染的文字
            output_path: 输出文件路径
            
        Returns:
            保存的文件路径
        """
        image = self.render(text)
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        image.save(output_path, "PNG")
        return output_path


# ============================================================================
# 便捷函数
# ============================================================================

def render_text_to_image(
    text: str,
    font_path: str,
    output_path: Optional[str] = None,
    font_size: int = 24,
    color: str = "#FFFFFF",
    stroke_color: Optional[str] = None,
    stroke_width: int = 2,
    width: int = 800,
    padding: Tuple[int, int, int, int] = (20, 20, 20, 20),
    line_spacing: int = 8,
    horizontal_align: str = "left",
    vertical_align: str = "top",
    auto_height: bool = True,
) -> Union[Image.Image, Tuple[Image.Image, str]]:
    """
    便捷函数：渲染文字为图片
    
    Args:
        text: 要渲染的文字
        font_path: 字体文件路径
        output_path: 输出文件路径（可选，如果提供则保存文件）
        font_size: 字号
        color: 文字颜色
        stroke_color: 描边颜色（None 表示无描边）
        stroke_width: 描边宽度
        width: 图片宽度
        padding: 上右下左边距
        line_spacing: 行距
        horizontal_align: 水平对齐 (left/center/right)
        vertical_align: 垂直对齐 (top/center/bottom)
        auto_height: 自动计算高度
        
    Returns:
        如果 output_path 为 None，返回 PIL Image 对象
        否则返回 (PIL Image 对象, 保存的文件路径)
    """
    style = TextStyle(
        font_path=font_path,
        font_size=font_size,
        color=color,
        stroke_color=stroke_color,
        stroke_width=stroke_width,
    )
    
    layout = LayoutConfig(
        width=width,
        padding=padding,
        line_spacing=line_spacing,
        horizontal_align=horizontal_align,
        vertical_align=vertical_align,
        auto_height=auto_height,
    )
    
    renderer = TextRenderer(style, layout)
    image = renderer.render(text)
    
    if output_path:
        renderer.render_to_file(text, output_path)
        return image, output_path
    
    return image
