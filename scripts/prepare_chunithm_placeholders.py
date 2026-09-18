"""Temporary bitmap split, explicitly approved pending separate production artwork.

Only the new placeholder files are written; the original comparison template stays
unchanged. Cropped logos still include their original pastel background. Replace
these with transparent production PNGs using the asset paths in themes.py.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "static/assets/images/Chunithm"


def main():
    output = ASSETS / "ConstantDisplay"
    output.mkdir(exist_ok=True)
    with Image.open(ASSETS / "content_base_chunithm_verse.png") as original:
        original = original.convert("RGBA")
        original.crop((1448, 830, 1877, 880)).save(output / "header_compare.png")
        original.crop((1470, 890, 1660, 996)).save(output / "logo_cn_2027.png")
        original.crop((1660, 890, 1862, 996)).save(output / "logo_latest_mate.png")
        neutral = original.copy()
        # Extend an undecorated row in this region as the temporary neutral panel.
        row = original.crop((1448, 1050, 1877, 1051))
        neutral.paste(row.resize((429, 230)), (1448, 830))
        neutral.save(output / "content_base.png")
        header = Image.new("RGBA", (429, 50), (172, 37, 217, 255))
        font = ImageFont.truetype(str(ROOT / "static/assets/fonts/SweiBellLegCJKsc-Black.ttf"), 34)
        ImageDraw.Draw(header).text((214, 23), "谱面定数", font=font, fill="white", anchor="mm")
        header.save(output / "header_single.png")
    print("Prepared explicitly temporary CHUNITHM bitmap layers.")


if __name__ == "__main__":
    main()
