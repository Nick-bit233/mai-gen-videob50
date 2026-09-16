"""Behavioral regressions for Linux decoding, GPU selection and failed renders."""
import io
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from utils.video_frames import VideoFrameReader


class FakeCapture:
    def __init__(self, fail_at=None):
        self.pos = 0
        self.reads = []
        self.seeks = []
        self.fail_at = fail_at
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FPS: 30, cv2.CAP_PROP_FRAME_COUNT: 4,
                cv2.CAP_PROP_FRAME_WIDTH: 8, cv2.CAP_PROP_FRAME_HEIGHT: 8}[prop]

    def set(self, prop, value):
        self.pos = int(value)
        self.seeks.append(self.pos)
        return True

    def read(self):
        self.reads.append(self.pos)
        if self.pos == self.fail_at or self.pos >= 4:
            return False, None
        frame = np.full((8, 8, 3), self.pos, np.uint8)
        self.pos += 1
        return True, frame

    def release(self):
        self.released = True


class FrameReaderTests(unittest.TestCase):
    def open_reader(self, capture):
        with patch('utils.video_frames.cv2.VideoCapture', return_value=capture):
            return VideoFrameReader('sample.mp4')

    def test_30fps_to_60fps_reads_each_source_frame_once(self):
        cap = FakeCapture()
        reader = self.open_reader(cap)
        self.addCleanup(reader.close)
        values = [int(reader.get_frame(i / 60)[0, 0, 0]) for i in range(8)]
        self.assertEqual(values, [0, 0, 1, 1, 2, 2, 3, 3])
        self.assertEqual(cap.reads, [0, 1, 2, 3])
        self.assertEqual(cap.seeks, [])

    def test_seek_read_next_cache_and_eof_agree(self):
        reader = self.open_reader(FakeCapture())
        self.addCleanup(reader.close)
        self.assertEqual(int(reader.read_next()[0, 0, 0]), 0)
        self.assertEqual(int(reader.get_frame(2/30)[0, 0, 0]), 2)
        reader.seek_to(2/30)
        self.assertEqual(int(reader.read_next()[0, 0, 0]), 2)
        self.assertEqual(int(reader.read_next()[0, 0, 0]), 3)
        self.assertIsNone(reader.read_next())
        self.assertEqual(int(reader.get_frame(20)[0, 0, 0]), 3)
        self.assertEqual(int(reader.get_frame(-1)[0, 0, 0]), 0)
        self.assertEqual(int(reader.read_next()[0, 0, 0]), 1)

    def test_opened_video_without_decoder_is_rejected_and_released(self):
        cap = FakeCapture(fail_at=0)
        with self.assertRaisesRegex(IOError, '解码失败'):
            self.open_reader(cap)
        self.assertTrue(cap.released)

    def test_midstream_failure_never_reuses_cached_frame(self):
        cap = FakeCapture(fail_at=2)
        reader = self.open_reader(cap)
        self.addCleanup(reader.close)
        with self.assertRaisesRegex(IOError, '3/4'):
            reader.get_frame(2/30)
        self.assertIsNone(reader._cached_frame)
        cap.fail_at = None
        self.assertEqual(int(reader.get_frame(2/30)[0, 0, 0]), 2)

    def test_invalid_metadata_and_time_are_rejected(self):
        cap = FakeCapture()
        cap.get = lambda prop: float('nan')
        with self.assertRaises(IOError):
            self.open_reader(cap)
        self.assertTrue(cap.released)
        reader = self.open_reader(FakeCapture())
        self.addCleanup(reader.close)
        with self.assertRaises(ValueError):
            reader.get_frame(float('inf'))
        reader.close()
        reader.close()
        with self.assertRaises(IOError):
            reader.get_frame(0)


class BackendTests(unittest.TestCase):
    def test_concurrent_initialization_does_not_reset_active_backend(self):
        from utils import TaichiAccel as accel
        entered, release = threading.Event(), threading.Event()
        results = []

        def initialize(func, candidates):
            entered.set()
            self.assertTrue(release.wait(3))
            accel.ti._mgv_backend = candidates[0]
            accel.ti._mgv_ti_initialized = True
            return True

        def request(name):
            try:
                results.append((name, accel.init_taichi(name)))
            except RuntimeError:
                results.append((name, 'restart-required'))

        with patch.object(accel.platform, 'system', return_value='Windows'), \
             patch.object(accel.ti, '_mgv_ti_initialized', False, create=True), \
             patch.object(accel.ti, '_mgv_backend', None, create=True), \
             patch.object(accel, '_ti_initialized', False), \
             patch.object(accel, '_submit_to_worker', side_effect=initialize) as submit:
            first = threading.Thread(target=request, args=('cuda',))
            second = threading.Thread(target=request, args=('vulkan',))
            first.start()
            self.assertTrue(entered.wait(3))
            second.start()
            release.set()
            first.join(3)
            second.join(3)
            self.assertFalse(first.is_alive() or second.is_alive())
            self.assertEqual(submit.call_count, 1)
            self.assertCountEqual(results, [('cuda', True), ('vulkan', 'restart-required')])

    def test_probe_timeout_and_cpu_fallback_cannot_pass_as_cuda(self):
        from utils import TaichiAccel as accel
        with patch.object(accel.subprocess, 'run', side_effect=subprocess.TimeoutExpired('probe', 1)):
            self.assertFalse(accel._probe_backend('cuda', timeout=1)[0])
        result = subprocess.CompletedProcess([], 0, stdout='TAICHI_PROBE_OK=cpu\n', stderr='')
        with patch.object(accel.subprocess, 'run', return_value=result):
            self.assertFalse(accel._probe_backend('cuda')[0])
        result.stdout = 'TAICHI_PROBE_OK=cuda\n'
        with patch.object(accel.subprocess, 'run', return_value=result):
            self.assertTrue(accel._probe_backend('cuda')[0])

    def test_linux_tries_vulkan_after_cuda_probe_failure(self):
        from utils import TaichiAccel as accel
        with patch.object(accel.platform, 'system', return_value='Linux'), \
             patch.object(accel.ti, '_mgv_ti_initialized', False, create=True), \
             patch.object(accel.ti, '_mgv_probe_results', {}, create=True), \
             patch.object(accel, '_ti_initialized', False), \
             patch.object(accel, '_probe_backend', side_effect=[(False, 'timeout'), (True, '')]) as probe, \
             patch.object(accel, '_submit_to_worker', return_value=True) as submit:
            self.assertTrue(accel.init_taichi('auto'))
            self.assertEqual([c.args[0] for c in probe.call_args_list], ['cuda', 'vulkan'])
            self.assertEqual(submit.call_args.args[1], ['vulkan'])

    def test_running_backend_cannot_be_silently_switched(self):
        from utils import TaichiAccel as accel
        with patch.object(accel.ti, '_mgv_ti_initialized', True, create=True), \
             patch.object(accel.ti, '_mgv_backend', 'cuda', create=True), \
             patch.object(accel, '_ti_initialized', False):
            with self.assertRaisesRegex(RuntimeError, '重新启动'):
                accel.init_taichi('vulkan')
            self.assertTrue(accel.init_taichi('cuda'))

    def test_linux_tries_vulkan_if_parent_cuda_initialization_fails(self):
        from utils import TaichiAccel as accel
        with patch.object(accel.platform, 'system', return_value='Linux'), \
             patch.object(accel.ti, '_mgv_ti_initialized', False, create=True), \
             patch.object(accel.ti, '_mgv_probe_results', {}, create=True), \
             patch.object(accel, '_ti_initialized', False), \
             patch.object(accel, '_probe_backend', return_value=(True, '')), \
             patch.object(accel, '_submit_to_worker', side_effect=[False, True]) as submit:
            self.assertTrue(accel.init_taichi('auto'))
            self.assertEqual([call.args[1] for call in submit.call_args_list], [['cuda'], ['vulkan']])

    def test_windows_order_is_preserved_without_subprocess_probe(self):
        from utils import TaichiAccel as accel
        with patch.object(accel.platform, 'system', return_value='Windows'), \
             patch.object(accel.ti, '_mgv_ti_initialized', False, create=True), \
             patch.object(accel, '_ti_initialized', False), \
             patch.object(accel, '_probe_backend') as probe, \
             patch.object(accel, '_submit_to_worker', return_value=True) as submit:
            accel.init_taichi()
            probe.assert_not_called()
            self.assertEqual(submit.call_args.args[1], ['cuda', 'vulkan', 'opengl', 'cpu'])


class FailedRenderTests(unittest.TestCase):
    def test_broken_pipe_includes_encoder_diagnostic(self):
        from utils.AccelRenderer import FFmpegWriter
        from unittest.mock import Mock
        writer = FFmpegWriter.__new__(FFmpegWriter)
        writer.width = writer.height = 8
        process = Mock()
        process.stdin.closed = False
        process.stdin.write.side_effect = OSError(22, 'Invalid argument')
        process.wait.return_value = 1
        process.poll.return_value = 1
        writer.process = process
        writer._stderr = tempfile.TemporaryFile()
        writer._stderr.write(b'Invalid bitrate')
        with self.assertRaisesRegex(RuntimeError, 'Invalid bitrate'):
            writer.write_frame(np.zeros((8, 8, 3), dtype=np.uint8))
        self.assertIsNone(writer.process)

    def test_failed_encoder_is_reported(self):
        from utils.AccelRenderer import FFmpegWriter
        writer = FFmpegWriter.__new__(FFmpegWriter)
        from unittest.mock import Mock
        process = Mock()
        process.stdin = io.BytesIO()
        process.wait.return_value = 1
        process.poll.return_value = 1
        writer.process = process
        writer._stderr = tempfile.TemporaryFile()
        writer._stderr.write(b'encoder failed')
        with self.assertRaisesRegex(RuntimeError, 'encoder failed'):
            writer.close()
        self.assertIsNone(writer.process)
        writer.close()

    def test_bad_info_background_keeps_existing_output(self):
        from utils.AccelRenderer import render_info_segment_accel
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'layer.png'
            Image.new('RGBA', (8, 8)).save(image)
            output = root / 'previous.mp4'
            output.write_bytes(b'existing finished output')
            style = {'asset_paths': {'intro_text_bg': str(image), 'intro_video_bg': 'broken.mp4', 'intro_bgm': ''}}
            with patch('utils.AccelRenderer.VideoFrameReader', side_effect=IOError('decode failed')):
                result = render_info_segment_accel({'duration': 1}, style, (8, 8), str(output))
            self.assertEqual(result['status'], 'error')
            self.assertEqual(output.read_bytes(), b'existing finished output')
            self.assertEqual(list(root.glob('.render-*')), [])


if __name__ == '__main__':
    unittest.main()
