"""Checked OpenCV decoding shared by all Taichi video layers."""
import math

import cv2


class VideoFrameReader:
    """RGB frames with a one-frame cache and explicit decode errors.

    get_frame preserves the existing out-of-range behavior (hold the first/last
    frame). read_next alone returns None at normal EOF. Returned arrays belong to
    the reader and must not be modified by callers.
    """

    def __init__(self, video_path: str):
        self.path = video_path
        self.cap = None
        self._cached_index = None
        self._cached_frame = None
        self._current_pos = 0  # physical next frame in the decoder
        self._next_index = 0   # logical next frame for read_next
        try:
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                raise IOError(f"无法打开视频: {video_path}")
            self.fps = float(self.cap.get(cv2.CAP_PROP_FPS))
            count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if not all(math.isfinite(v) and v > 0 for v in (self.fps, count, width, height)):
                raise IOError(f"视频帧率、尺寸或帧数无效: {video_path}")
            self.frame_count, self.width, self.height = int(count), int(width), int(height)
            if min(self.frame_count, self.width, self.height) < 1:
                raise IOError(f"视频尺寸或帧数无效: {video_path}")
            self.duration = self.frame_count / self.fps
            # isOpened and frame counts can succeed even without an AV1 decoder.
            self._read_index(0)
            self._next_index = 0
        except Exception:
            self.close()
            raise

    def _frame_index(self, time_sec):
        if not math.isfinite(time_sec):
            raise ValueError("视频时间必须是有限数值")
        return max(0, min(int(time_sec * self.fps), self.frame_count - 1))

    def _read_index(self, index):
        if self.cap is None:
            raise IOError(f"视频读取器已关闭: {self.path}")
        if index != self._cached_index:
            self._cached_index = self._cached_frame = None
            if index != self._current_pos:
                if not self.cap.set(cv2.CAP_PROP_POS_FRAMES, index):
                    raise IOError(f"无法定位视频第 {index + 1} 帧: {self.path}")
                self._current_pos = index
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self._current_pos = -1  # failed decoders may advance unpredictably
                raise IOError(
                    f"视频解码失败，第 {index + 1}/{self.frame_count} 帧: {self.path}。"
                    "请检查素材是否完整，并使用本版本配套依赖（OpenCV 4.14.0.94）。"
                )
            self._current_pos = index + 1
            self._cached_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._cached_index = index
        self._next_index = index + 1
        return self._cached_frame

    def seek_to(self, time_sec: float):
        # Defer physical seeking; the requested frame may already be cached.
        self._next_index = self._frame_index(time_sec)

    def read_next(self):
        if self._next_index >= self.frame_count:
            return None
        return self._read_index(self._next_index)

    def get_frame(self, time_sec: float):
        return self._read_index(self._frame_index(time_sec))

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self._cached_index = self._cached_frame = None

    def __del__(self):
        self.close()
