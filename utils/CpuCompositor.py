"""NumPy/OpenCV CPU compositor for the non-GPU rendering path.

Pre-multiplies static layers once and blends them in horizontal bands across a
thread pool. The layer order matches TaichiAccel.FrameCompositor:
background (dimmed) -> chart video -> achievement image -> comment text.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np


def _split_rgba(image: np.ndarray):
    if image.ndim == 3 and image.shape[2] == 4:
        rgb = image[:, :, :3].astype(np.float32)
        alpha = (image[:, :, 3:4].astype(np.float32) / 255.0)
    elif image.ndim == 3 and image.shape[2] == 3:
        rgb = image.astype(np.float32)
        alpha = np.ones((image.shape[0], image.shape[1], 1), dtype=np.float32)
    else:
        raise ValueError(f"Unsupported image shape: {image.shape}")
    return rgb, alpha


class CpuFrameCompositor:
    """CPU equivalent of TaichiAccel.FrameCompositor."""

    def __init__(
        self,
        bg: np.ndarray,
        score_image: np.ndarray,
        text_image: np.ndarray,
        video_pos: tuple,
        text_pos: tuple,
        bg_brightness: float = 0.8,
        output_size: tuple = (1920, 1080),
        bands: int = None,
    ):
        self.out_w, self.out_h = int(output_size[0]), int(output_size[1])
        self.vid_x, self.vid_y = int(video_pos[0]), int(video_pos[1])
        self.text_x, self.text_y = int(text_pos[0]), int(text_pos[1])
        self.bg_brightness = float(bg_brightness)
        self.nv12_supported = False

        self._bg = bg[:, :, :3].astype(np.float32) * self.bg_brightness

        score_rgb, score_alpha = _split_rgba(score_image)
        self._score_pre = score_rgb * score_alpha
        self._score_inv = 1.0 - score_alpha
        self._score_h, self._score_w = score_rgb.shape[:2]

        text_rgb, text_alpha = _split_rgba(text_image)
        self._text_pre = text_rgb * text_alpha
        self._text_inv = 1.0 - text_alpha
        self._text_h, self._text_w = text_rgb.shape[:2]

        if bands is None:
            bands = int(os.environ.get("MAIGEN_CPU_BANDS", "8"))
        self._bands = max(1, min(int(bands), self.out_h))
        self._executor = (ThreadPoolExecutor(
            max_workers=self._bands, thread_name_prefix="cpu-compositor")
            if self._bands > 1 else None)

    def update_bg(self, bg: np.ndarray):
        self._bg = bg[:, :, :3].astype(np.float32) * self.bg_brightness

    def _compose_band(self, out: np.ndarray, out_u8: np.ndarray, y0: int, y1: int):
        # Achievement image: covers rows [0, score_h) and columns [0, score_w).
        score_y0, score_y1 = y0, min(y1, self._score_h)
        if score_y0 < score_y1:
            roi = out[score_y0:score_y1, :self._score_w]
            roi *= self._score_inv[score_y0:score_y1]
            roi += self._score_pre[score_y0:score_y1]

        # Comment text: only the bands overlapping its rectangle.
        text_y0 = max(y0, self.text_y)
        text_y1 = min(y1, self.text_y + self._text_h)
        if text_y0 < text_y1:
            local_y0 = text_y0 - self.text_y
            local_y1 = text_y1 - self.text_y
            roi = out[text_y0:text_y1, self.text_x:self.text_x + self._text_w]
            roi *= self._text_inv[local_y0:local_y1]
            roi += self._text_pre[local_y0:local_y1]

        out_u8[y0:y1] = out[y0:y1].astype(np.uint8)

    def composite(self, video_frame: np.ndarray) -> np.ndarray:
        out = self._bg.copy()
        video = video_frame[:, :, :3]
        vh, vw = video.shape[:2]
        y0, x0 = self.vid_y, self.vid_x
        y1, x1 = min(y0 + vh, self.out_h), min(x0 + vw, self.out_w)
        if y0 < y1 and x0 < x1:
            out[y0:y1, x0:x1] = video[:y1 - y0, :x1 - x0]

        out_u8 = np.empty((self.out_h, self.out_w, 3), dtype=np.uint8)
        if self._executor is None:
            self._compose_band(out, out_u8, 0, self.out_h)
        else:
            step = (self.out_h + self._bands - 1) // self._bands
            futures = []
            for band in range(self._bands):
                band_y0 = band * step
                band_y1 = min(self.out_h, band_y0 + step)
                if band_y0 >= band_y1:
                    continue
                futures.append(self._executor.submit(
                    self._compose_band, out, out_u8, band_y0, band_y1))
            for future in futures:
                future.result()
        return out_u8

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

