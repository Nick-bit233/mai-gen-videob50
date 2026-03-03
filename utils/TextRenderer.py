"""
TextRenderer - 文字渲染模块
将文字渲染为透明 PNG 图片，支持多语言智能换行、描边、Emoji 等功能

Author: nanobot
Date: 2026-03-02
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, List, Union
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import requests
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import os
import re
import unicodedata
import math


# ============================================================================
# Emoji 源配置 - 支持国内 CDN + 兜底机制
# ============================================================================

import logging
_logger = logging.getLogger(__name__)

# Emoji 缓存：避免重复下载
_emoji_cache: dict = {}

# 失败的 emoji 记录：避免反复尝试
_failed_emojis: set = set()


def _get_bootcdn_source():
    """
    获取 BootCDN 源类（国内加速，延迟导入 pilmoji）
    
    BootCDN twemoji 格式：
    https://cdn.bootcdn.net/ajax/libs/twemoji/16.0.1/72x72/{codepoint}.png
    """
    from pilmoji.source import BaseSource
    
    class _BootCDNSource(BaseSource):
        """
        使用 BootCDN 的 twemoji 源（用于 Pilmoji）
        从 https://cdn.bootcdn.net/ajax/libs/twemoji/16.0.1/72x72/ 下载 emoji 图片

        """
        
        BASE_URL = 'https://cdn.bootcdn.net/ajax/libs/twemoji/16.0.1/72x72/'
        
        def get_emoji(self, emoji: str) -> Optional[BytesIO]:
            """获取 emoji 图片，失败时返回 None（留空）"""
            global _emoji_cache, _failed_emojis
            
            # 检查是否已经失败过
            if emoji in _failed_emojis:
                return None
            
            # 检查缓存（返回新的 BytesIO 副本）
            if emoji in _emoji_cache:
                return BytesIO(_emoji_cache[emoji])
            
            # 将 emoji 转换为 Unicode 码点（小写）
            codepoint = '-'.join(f'{ord(c):x}' for c in emoji)
            url = f'{self.BASE_URL}{codepoint}.png'
            
            try:
                req = Request(
                    url, 
                    headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'image/png,*/*'
                    }
                )
                with urlopen(req, timeout=10) as response:
                    data = response.read()
                    # 缓存原始字节数据（不是 BytesIO）
                    _emoji_cache[emoji] = data
                    return BytesIO(data)
                    
            except Exception as e:
                _logger.warning(f"Failed to fetch emoji '{emoji}({codepoint})' from BootCDN: {e}, try fetching with base code...")
                # 尝试去除code point的后缀重试
                if '-' in codepoint:
                    base_codepoint = codepoint.split('-')[0]
                    response = requests.get(f'{self.BASE_URL}{base_codepoint}.png')
                    if response.status_code == 200:
                        _logger.warning(f"Fetched emoji '{emoji}({codepoint})' with base code: {base_codepoint}")
                        data = response.content
                        _emoji_cache[emoji] = data
                        return BytesIO(data)
                    else:
                        # 记录失败，避免反复尝试
                        _failed_emojis.add(emoji)
                        _logger.warning(f"Failed to fetch emoji '{emoji}({codepoint})' again with base code: {base_codepoint}")
                    return None
        
        def get_discord_emoji(self, id: int) -> None:
            """Discord emoji 不支持"""
            return None
    
    return _BootCDNSource


def _clear_emoji_cache():
    """清除 emoji 缓存（用于测试或内存释放）"""
    global _emoji_cache, _failed_emojis
    _emoji_cache.clear()
    _failed_emojis.clear()


# ============================================================================
# TextTokenizer - 智能分词器
# ============================================================================

class TextTokenizer:
    """
    智能分词器 - 支持中英日多语言分词
    """
    
    CJK_RANGES = [
        (0x4E00, 0x9FFF),    # CJK 统一汉字
        (0x3400, 0x4DBF),    # CJK 扩展 A
        (0x20000, 0x2A6DF),  # CJK 扩展 B
        (0x2A700, 0x2B73F),  # CJK 扩展 C
        (0x2B740, 0x2B81F),  # CJK 扩展 D
        (0x2B820, 0x2CEAF),  # CJK 扩展 E
        (0xF900, 0xFAFF),    # CJK 兼容汉字
    ]
    
    HIRAGANA_RANGE = (0x3040, 0x309F)
    KATAKANA_RANGE = (0x30A0, 0x30FF)
    
    CHINESE_PUNCTUATION = "，。！？；：、""''（）【】《》…—"
    JAPANESE_PUNCTUATION = "、。！？「」『』（）【】…・"
    ENGLISH_PUNCTUATION = ",.!?;:'\"()[]{}<>-"
    
    _jieba_initialized = False
    
    def __init__(self, custom_dict_path: Optional[str] = None):
        self._init_jieba(custom_dict_path)
    
    def _init_jieba(self, custom_dict_path: Optional[str] = None) -> None:
        if TextTokenizer._jieba_initialized:
            return
        
        try:
            import jieba
            
            if custom_dict_path and os.path.exists(custom_dict_path):
                jieba.load_userdict(custom_dict_path)
            
            gaming_words = [
                ("舞萌DX", 5, "n"),
                ("中二节奏", 5, "n"),
                ("谱面确认", 5, "n"),
                ("分表", 5, "n"),
                ("B50", 5, "n"),
                ("B30", 5, "n"),
            ]
            
            for word, freq, tag in gaming_words:
                jieba.add_word(word, freq, tag)
            
            TextTokenizer._jieba_initialized = True
            
        except ImportError:
            pass
    
    def tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        
        has_cjk = any(self._is_chinese(c) or self._is_japanese(c) for c in text)
        
        if has_cjk:
            return self._tokenize_with_jieba(text)
        else:
            return self._tokenize_ascii(text)
    
    def _tokenize_with_jieba(self, text: str) -> List[str]:
        try:
            import jieba
            raw_tokens = list(jieba.cut(text))
            
            tokens = []
            for token in raw_tokens:
                if not token:
                    continue
                
                if '\n' in token:
                    parts = token.split('\n')
                    for i, part in enumerate(parts):
                        if part:
                            tokens.append(part)
                        if i < len(parts) - 1:
                            tokens.append('\n')
                elif len(token) == 1 and self._is_punctuation(token):
                    tokens.append(token)
                elif token == ' ' or token == '\t':
                    tokens.append(token)
                else:
                    tokens.append(token)
            
            return tokens
            
        except ImportError:
            return self._tokenize_by_char(text)
    
    def _tokenize_ascii(self, text: str) -> List[str]:
        tokens = []
        i = 0
        
        while i < len(text):
            char = text[i]
            
            if char == '\n':
                tokens.append('\n')
                i += 1
            elif char in ' \t':
                tokens.append(char)
                i += 1
            elif self._is_punctuation(char):
                tokens.append(char)
                i += 1
            else:
                word, length = self._extract_ascii_word(text, i)
                if length > 0:
                    tokens.append(word)
                    i += length
                else:
                    tokens.append(char)
                    i += 1
        
        return tokens
    
    def _tokenize_by_char(self, text: str) -> List[str]:
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
        if len(char) != 1:
            return False
        code = ord(char)
        for start, end in self.CJK_RANGES:
            if start <= code <= end:
                return True
        return False
    
    def _is_japanese(self, char: str) -> bool:
        if len(char) != 1:
            return False
        code = ord(char)
        return (self.HIRAGANA_RANGE[0] <= code <= self.HIRAGANA_RANGE[1] or
                self.KATAKANA_RANGE[0] <= code <= self.KATAKANA_RANGE[1])
    
    def _is_punctuation(self, char: str) -> bool:
        return (char in self.CHINESE_PUNCTUATION or 
                char in self.JAPANESE_PUNCTUATION or 
                char in self.ENGLISH_PUNCTUATION)
    
    def _extract_ascii_word(self, text: str, start: int) -> Tuple[str, int]:
        end = start
        while end < len(text) and text[end].isascii() and not text[end].isspace() and not self._is_punctuation(text[end]):
            end += 1
        return text[start:end], end - start


@dataclass
class TextStyle:
    """文字样式配置"""
    font_path: str
    font_size: int = 24
    color: str = "#FFFFFF"
    stroke_color: Optional[str] = None
    stroke_width: int = 2

    def __post_init__(self):
        if self.font_size <= 0:
            raise ValueError(f"font_size must be positive, got {self.font_size}")
        if self.stroke_width < 0:
            raise ValueError(f"stroke_width must be non-negative, got {self.stroke_width}")


@dataclass
class LayoutConfig:
    """布局配置"""
    width: int = 800
    height: int = 600
    auto_height: bool = True
    padding: Tuple[int, int, int, int] = (20, 20, 20, 20)
    line_spacing: int = 8
    horizontal_align: str = "left"
    vertical_align: str = "top"
    max_lines: Optional[int] = None

    def __post_init__(self):
        valid_h_align = ("left", "center", "right")
        valid_v_align = ("top", "center", "bottom")
        
        if self.horizontal_align not in valid_h_align:
            raise ValueError(f"horizontal_align must be one of {valid_h_align}")
        if self.vertical_align not in valid_v_align:
            raise ValueError(f"vertical_align must be one of {valid_v_align}")
        if self.width <= 0:
            raise ValueError(f"width must be positive")


class TextRenderer:
    """
    文字渲染器 - 将文字渲染为透明 PNG 图片
    
    使用 Pilmoji 库支持 Emoji 渲染
    """
    
    _tokenizer: Optional[TextTokenizer] = None
    
    def __init__(self, style: TextStyle, layout: LayoutConfig):
        self.style = style
        self.layout = layout
        self._font: Optional[ImageFont.FreeTypeFont] = None
        self._original_font_size = style.font_size
        
        if TextRenderer._tokenizer is None:
            TextRenderer._tokenizer = TextTokenizer()
    
    @classmethod
    def set_custom_dict(cls, dict_path: str) -> None:
        cls._tokenizer = TextTokenizer(dict_path)
    
    @property
    def font(self) -> ImageFont.FreeTypeFont:
        if self._font is None:
            self._load_font()
        return self._font
    
    def _load_font(self, size: Optional[int] = None) -> None:
        font_size = size if size is not None else self.style.font_size
        
        if not os.path.exists(self.style.font_path):
            raise FileNotFoundError(f"Font file not found: {self.style.font_path}")
        
        try:
            self._font = ImageFont.truetype(self.style.font_path, font_size)
            self.style.font_size = font_size
        except Exception as e:
            raise RuntimeError(f"Failed to load font: {e}")
    
    def _set_font_size(self, size: int) -> None:
        self._load_font(size)
    
    @staticmethod
    def _has_emoji(text: str) -> bool:
        """检查文本是否包含 emoji"""
        for char in text:
            code = ord(char)
            # 常见 emoji 范围
            if (0x1F300 <= code <= 0x1F9FF or  # 各种 emoji
                0x2600 <= code <= 0x27BF or    # 符号
                0x1F600 <= code <= 0x1F64F):   # 表情
                return True
        return False
    
    def _wrap_text_for_pilmoji(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """
        为 Pilmoji 准备文本换行
        
        由于 Pilmoji 的 getsize 方法可以正确处理 emoji，
        我们使用它来计算行宽
        """
        try:
            from pilmoji import Pilmoji
            
            # 创建临时图片用于 Pilmoji
            temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            
            lines = []
            paragraphs = text.split('\n')
            
            for para in paragraphs:
                if not para:
                    lines.append('')
                    continue
                
                # 使用分词器进行分词
                tokens = self._tokenizer.tokenize(para)
                
                current_line = ""
                
                for token in tokens:
                    test_line = current_line + token
                    
                    # 使用 Pilmoji 计算宽度
                    with Pilmoji(temp_img, source=_get_bootcdn_source()()) as pilmoji:
                        bbox = pilmoji.getsize(test_line, font=font)
                        width = bbox[0]
                    
                    if width <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                            current_line = token
                        else:
                            # 单个 token 太长，按字符分割
                            for char in token:
                                test_line = current_line + char
                                with Pilmoji(temp_img, source=_get_bootcdn_source()()) as pilmoji:
                                    bbox = pilmoji.getsize(test_line, font=font)
                                    width = bbox[0]
                                
                                if width <= max_width:
                                    current_line = test_line
                                else:
                                    if current_line:
                                        lines.append(current_line)
                                    current_line = char
                
                if current_line:
                    lines.append(current_line)
            
            return lines if lines else ['']
            
        except ImportError:
            # Pilmoji 未安装，回退到普通换行
            return self._wrap_text_simple(text, font, max_width)
    
    def _wrap_text_simple(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
        """简单换行（不考虑 emoji）"""
        lines = []
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para:
                lines.append('')
                continue
            
            tokens = self._tokenizer.tokenize(para)
            current_line = ""
            
            for token in tokens:
                test_line = current_line + token
                bbox = font.getbbox(test_line)
                width = bbox[2] - bbox[0]
                
                if width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                        current_line = token
                    else:
                        for char in token:
                            test_line = current_line + char
                            bbox = font.getbbox(test_line)
                            width = bbox[2] - bbox[0]
                            
                            if width <= max_width:
                                current_line = test_line
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = char
            
            if current_line:
                lines.append(current_line)
        
        return lines if lines else ['']
    
    def render(self, text: str, auto_scale: bool = True) -> Image.Image:
        """渲染文字为 PIL Image 对象"""
        if not text:
            return Image.new("RGBA", (self.layout.width, 1), (0, 0, 0, 0))
        
        max_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        
        # 检查是否包含 emoji
        has_emoji = self._has_emoji(text)
        
        # 换行处理 - 带兜底机制
        use_pilmoji = False
        if has_emoji:
            try:
                from pilmoji import Pilmoji
                lines = self._wrap_text_for_pilmoji(text, self.font, max_width)
                use_pilmoji = True
            except Exception as e:
                # Pilmoji 任何错误都回退到简单模式
                _logger.warning(f"Pilmoji failed, fallback to simple mode: {e}")
                lines = self._wrap_text_simple(text, self.font, max_width)
                use_pilmoji = False
        else:
            lines = self._wrap_text_simple(text, self.font, max_width)
            use_pilmoji = False
        
        # 计算行高和总高度
        line_heights = []
        line_widths = []
        
        # 获取基础行高
        sample_bbox = self.font.getbbox("测试Ay")
        base_line_height = sample_bbox[3] - sample_bbox[1]
        
        if use_pilmoji:
            temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            for line in lines:
                if line:
                    with Pilmoji(temp_img, source=_get_bootcdn_source()()) as pilmoji:
                        w, h = pilmoji.getsize(line, font=self.font)
                        line_widths.append(w)
                        line_heights.append(max(h, base_line_height))
                else:
                    line_widths.append(0)
                    line_heights.append(base_line_height)
        else:
            for line in lines:
                if line:
                    bbox = self.font.getbbox(line)
                    line_widths.append(bbox[2] - bbox[0])
                    line_heights.append(bbox[3] - bbox[1])
                else:
                    line_widths.append(0)
                    line_heights.append(base_line_height)
        
        total_text_height = sum(line_heights) + self.layout.line_spacing * max(0, len(lines) - 1)
        
        # 计算图片高度
        if self.layout.auto_height:
            image_height = total_text_height + self.layout.padding[0] + self.layout.padding[2]
        else:
            image_height = self.layout.height
        
        # 创建透明图片
        image = Image.new("RGBA", (self.layout.width, image_height), (0, 0, 0, 0))
        
        # 计算起始 Y 坐标
        if self.layout.vertical_align == "top":
            current_y = self.layout.padding[0]
        elif self.layout.vertical_align == "center":
            current_y = self.layout.padding[0] + (image_height - self.layout.padding[0] - self.layout.padding[2] - total_text_height) // 2
        else:
            current_y = image_height - self.layout.padding[2] - total_text_height
        
        # 绘制文本
        if use_pilmoji:
            self._draw_with_pilmoji(image, lines, line_widths, line_heights, current_y)
        else:
            self._draw_simple(image, lines, line_widths, line_heights, current_y)
        
        return image
    
    def _draw_with_pilmoji(self, image: Image.Image, lines: List[str], 
                           line_widths: List[int], line_heights: List[int], 
                           start_y: float) -> None:
        """使用 Pilmoji 绘制文本（支持 emoji），失败时回退到简单模式"""
        from pilmoji import Pilmoji
        
        content_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        color = self._parse_color(self.style.color)
        
        current_y = start_y
        
        try:
            with Pilmoji(image, source=_get_bootcdn_source()()) as pilmoji:
                for i, line in enumerate(lines):
                    if not line:
                        current_y += line_heights[i] + self.layout.line_spacing
                        continue
                    
                    line_width = line_widths[i]
                    line_height = line_heights[i]
                    
                    # 水平对齐
                    if self.layout.horizontal_align == "left":
                        x = self.layout.padding[3]
                    elif self.layout.horizontal_align == "center":
                        x = self.layout.padding[3] + (content_width - line_width) // 2
                    else:
                        x = self.layout.width - self.layout.padding[1] - line_width
                    
                    # 垂直对齐
                    y = current_y
                    
                    # 绘制描边（如果启用）
                    if self.style.stroke_color and self.style.stroke_width > 0:
                        stroke_color = self._parse_color(self.style.stroke_color)
                        for angle in range(0, 360, 45):
                            dx = self.style.stroke_width * math.cos(math.radians(angle))
                            dy = self.style.stroke_width * math.sin(math.radians(angle))
                            pilmoji.text((x + dx, y + dy), line, fill=stroke_color, font=self.font)
                    
                    # 绘制文字
                    pilmoji.text((x, y), line, fill=color, font=self.font)
                    
                    current_y += line_height + self.layout.line_spacing
                    
        except Exception as e:
            # Pilmoji 绘制失败，回退到简单绘制（emoji 会显示为方框或留空）
            _logger.warning(f"Pilmoji drawing failed, fallback to simple mode: {e}")
            self._draw_simple(image, lines, line_widths, line_heights, start_y)
    
    def _draw_simple(self, image: Image.Image, lines: List[str], 
                     line_widths: List[int], line_heights: List[int], 
                     start_y: float) -> None:
        """简单绘制（不含 emoji）"""
        draw = ImageDraw.Draw(image)
        content_width = self.layout.width - self.layout.padding[1] - self.layout.padding[3]
        color = self._parse_color(self.style.color)
        
        current_y = start_y
        
        for i, line in enumerate(lines):
            if not line:
                current_y += line_heights[i] + self.layout.line_spacing
                continue
            
            line_width = line_widths[i]
            line_height = line_heights[i]
            
            # 水平对齐
            if self.layout.horizontal_align == "left":
                x = self.layout.padding[3]
            elif self.layout.horizontal_align == "center":
                x = self.layout.padding[3] + (content_width - line_width) // 2
            else:
                x = self.layout.width - self.layout.padding[1] - line_width
            
            y = current_y
            
            # 绘制描边
            if self.style.stroke_color and self.style.stroke_width > 0:
                self._draw_stroke(draw, line, x, y, self.font, 
                                 self.style.stroke_color, self.style.stroke_width)
            
            # 绘制文字
            draw.text((x, y), line, font=self.font, fill=color)
            
            current_y += line_height + self.layout.line_spacing
    
    def _draw_stroke(self, draw: ImageDraw.ImageDraw, text: str, x: float, y: float, 
                     font: ImageFont.FreeTypeFont, stroke_color: str, stroke_width: int) -> None:
        """绘制文字描边"""
        color = self._parse_color(stroke_color)
        
        for angle in range(0, 360, 45):
            dx = stroke_width * math.cos(math.radians(angle))
            dy = stroke_width * math.sin(math.radians(angle))
            draw.text((x + dx, y + dy), text, font=font, fill=color)
    
    def _parse_color(self, color: str) -> Tuple[int, int, int, int]:
        """解析颜色字符串"""
        from PIL import ImageColor
        
        try:
            parsed = ImageColor.getcolor(color, "RGBA")
            if parsed is None:
                return (255, 255, 255, 255)
            if len(parsed) == 3:
                return (*parsed, 255)
            return parsed
        except ValueError:
            return (255, 255, 255, 255)
    
    def render_to_file(self, text: str, output_path: str) -> str:
        """渲染并保存为文件"""
        image = self.render(text)
        
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
    """便捷函数：渲染文字为图片"""
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
