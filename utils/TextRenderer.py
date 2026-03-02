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
    
    def _set_font_size(self, size: int) -> None:
        """设置字体大小（重新加载字体）"""
        self._load_font(size)
    
    def render(self, text: str, auto_scale: bool = True) -> Image.Image:
        """
        渲染文字为 PIL Image 对象
        
        Args:
            text: 要渲染的文字
            auto_scale: 当文字超出容器时是否自动缩放字号
            
        Returns:
            PIL Image 对象 (RGBA 模式，透明背景)
        """
        if not text:
            # 空文本返回透明图片
            return Image.new("RGBA", (self.layout.width, 1), (0, 0, 0, 0))
        
        # 分词和换行处理
        lines = self._wrap_text(text)
        
        # 检查是否需要自动缩放
        if auto_scale and self._needs_scaling(lines):
            self._auto_scale_font(text)
        
        # 重新计算换行（因为字号可能已变化）
        lines = self._wrap_text(text)
        
        # 计算所需高度
        content_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        line_heights = []
        for line in lines:
            bbox = self.font.getbbox(line)
            line_height = bbox[3] - bbox[1]
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
            
            # 计算水平位置
            bbox = self.font.getbbox(line)
            line_width = bbox[2] - bbox[0]
            
            if self.layout.horizontal_align == "left":
                x = self.layout.padding[3]
            elif self.layout.horizontal_align == "center":
                x = self.layout.padding[3] + (content_width - line_width) // 2
            else:  # right
                x = self.layout.width - self.layout.padding[1] - line_width
            
            # 垂直居中当前行
            y = current_y
            
            # 绘制描边（如果启用）
            if self.style.stroke_color and self.style.stroke_width > 0:
                self._draw_stroke(draw, line, x, y, self.font, self.style.stroke_color, self.style.stroke_width)
            
            # 绘制文字
            draw.text((x, y), line, font=self.font, fill=self._parse_color(self.style.color))
            
            current_y += line_height + self.layout.line_spacing
        
        return image
    
    def _needs_scaling(self, lines: List[str]) -> bool:
        """
        检查是否需要缩放字号
        
        Args:
            lines: 当前行列表
            
        Returns:
            是否需要缩放
        """
        # 检查行数是否超过限制
        if self.layout.max_lines and len(lines) > self.layout.max_lines:
            return True
        
        # 检查是否有固定高度限制且超出
        if not self.layout.auto_height:
            content_height = self.layout.height - self.layout.padding[0] - self.layout.padding[2]
            line_height = self.font.getbbox("测试")[3] - self.font.getbbox("测试")[1]
            max_possible_lines = (content_height + self.layout.line_spacing) // (line_height + self.layout.line_spacing)
            if len(lines) > max_possible_lines:
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
    
    def _fits_container(self, lines: List[str]) -> bool:
        """
        检查行列表是否适合容器
        
        Args:
            lines: 行列表
            
        Returns:
            是否适合容器
        """
        # 检查行数限制
        if self.layout.max_lines and len(lines) > self.layout.max_lines:
            return False
        
        # 检查高度限制
        if not self.layout.auto_height:
            content_height = self.layout.height - self.layout.padding[0] - self.layout.padding[2]
            line_height = self.font.getbbox("测试")[3] - self.font.getbbox("测试")[1]
            total_height = len(lines) * line_height + (len(lines) - 1) * self.layout.line_spacing
            if total_height > content_height:
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
