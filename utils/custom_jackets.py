"""One transformation for manual uploads, Excel previews and committed jackets."""
from PIL import Image


def prepare_jacket(source):
    with Image.open(source) as original:
        if original.width * original.height > 40_000_000:
            raise ValueError('曲绘像素尺寸过大。')
        image = original.convert('RGBA')
        width, height = image.size
        side = min(width, height)
        left, top = (width-side)//2, (height-side)//2
        image = image.crop((left, top, left+side, top+side))
        return image.resize((400,400), Image.Resampling.LANCZOS)
