"""Rebuild ADVANCED by recoloring the existing CHUNITHM frame, without resampling."""
import colorsys
from functools import lru_cache
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
# SEGA's official difficulty-selection screenshot shows ADVANCED as orange.
# https://chunithm.sega.com/assets/img/play/game/05.png
# Use the bright orange badge sample's hue; preserve the source saturation/value.
ADVANCED_REFERENCE_RGB = (255, 124, 0)
EXPERT_REFERENCE_RGB = (255, 45, 42)


def build():
    directory = ROOT / "static/assets/images/Chunithm/Frames"
    with Image.open(directory / "2.png") as source:
        source = source.convert("RGBA")
        if source.size != (1311, 780):
            raise ValueError("Unexpected CHUNITHM frame dimensions")
        target_hue = colorsys.rgb_to_hsv(*(v / 255 for v in ADVANCED_REFERENCE_RGB))[0]
        source_hue = colorsys.rgb_to_hsv(*(v / 255 for v in EXPERT_REFERENCE_RGB))[0]

        @lru_cache(maxsize=None)
        def recolor(pixel):
            r, g, b, alpha = pixel
            if not alpha:
                return pixel
            hue, saturation, value = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if saturation < 0.1:
                return pixel
            rgb = colorsys.hsv_to_rgb((hue + target_hue - source_hue) % 1, saturation, value)
            return *(round(channel * 255) for channel in rgb), alpha

        target = Image.new("RGBA", source.size)
        target.putdata([recolor(pixel) for pixel in source.getdata()])
        if target.getchannel("A").tobytes() != source.getchannel("A").tobytes():
            raise AssertionError("Frame opacity must remain unchanged")
        target.save(directory / "1.png")
        print(directory / "1.png")


if __name__ == "__main__":
    build()
