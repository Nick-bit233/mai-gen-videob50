"""Capture real MoviePy encoder commands and stderr via its public writer API."""
from utils.diagnostics import current_report


def install_moviepy_diagnostics():
    import moviepy.video.io.ffmpeg_writer as video
    import moviepy.audio.io.ffmpeg_audiowriter as audio
    for module, name in ((video, 'FFMPEG_VideoWriter'), (audio, 'FFMPEG_AudioWriter')):
        original = getattr(module, name)
        if getattr(original, '_diagnostic_capture', False):
            continue

        def make_writer(base, label):
            class Writer(base):
                _diagnostic_capture = True
                def __init__(self, *args, **kwargs):
                    self.proc = None
                    self._attempt = current_report().attempt([], label)
                    self._attempt.stderr.close()
                    logfile = (self._attempt.report.directory / self._attempt.item['stderr']).open('w+', encoding='utf-8', errors='replace')
                    self._attempt.stderr = logfile
                    kwargs['logfile'] = logfile
                    try:
                        super().__init__(*args, **kwargs)
                        self._attempt.item['command'] = [str(v) for v in self.proc.args]
                        self._attempt.report.save()
                    except Exception as exc:
                        self._attempt.finish(error=exc)
                        raise

                def close(self):
                    process = self.proc
                    try:
                        super().close()
                        if process:
                            self._attempt.finish(process.returncode)
                            if process.returncode:
                                from utils.diagnostics import _tail
                                error = _tail(self._attempt.report.directory / self._attempt.item['stderr'])
                                raise RuntimeError(f'{label} 编码失败 ({process.returncode}): {error}')
                    except Exception as exc:
                        if hasattr(self, '_attempt'):
                            self._attempt.finish(process.poll() if process else None, exc)
                        raise
            return Writer
        setattr(module, name, make_writer(original, 'CPU视频编码' if name == 'FFMPEG_VideoWriter' else 'CPU音频编码'))
