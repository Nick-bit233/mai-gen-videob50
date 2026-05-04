import os, subprocess, sys, re, glob, time, gc

CLIP_DIR = None
for d in os.listdir('b50_datas'):
    p = os.path.join('b50_datas', d, 'videos_cpu_batches')
    if os.path.isdir(p):
        CLIP_DIR = p
        break

FFMPEG = 'ffmpeg.exe'
FFPROBE = 'ffprobe.exe'
TRANS = 1.5
FPS = 60

def get_dur(p):
    r = subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv', p], capture_output=True, text=True)
    for line in r.stdout.strip().split(chr(10)):
        if line.startswith('format'): return float(line.split(',')[1])
    return 0

def get_files():
    files = [f for f in os.listdir(CLIP_DIR) if f.endswith('.mp4') and re.match(r'^\d+_', f)]
    return sorted(files, key=lambda f: int(f.split('_')[0]))

def merge_two(a, b, out, off):
    # Video: xfade fade
    # Audio: aconcat (correct duration when video is shorter, trim with -shortest)
    flt = (f'[0:v]fps={FPS},format=yuv420p[v0];'
           f'[1:v]fps={FPS},format=yuv420p[v1];'
           f'[v0][v1]xfade=transition=fade:duration={TRANS}:offset={off:.3f}[vout];'
           f'[0:a][1:a]concat=n=2:v=0:a=1[aout]')
    cmd = [FFMPEG, '-y', '-hide_banner', '-loglevel', 'warning',
        '-i', a, '-i', b, '-filter_complex', flt,
        '-map', '[vout]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k',
        '-shortest', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'  MERGE ERR: {r.stderr[:600]}')
        return None
    return get_dur(out)

def main():
    t0 = time.time()
    files = get_files()
    n = len(files)
    print(f'{n} clips found')
    sys.stdout.flush()

    # Cleanup old temps
    for p in glob.glob(os.path.join(CLIP_DIR, '_m*.mp4')):
        os.remove(p)
    final = os.path.join(CLIP_DIR, 'final_output.mp4')
    if os.path.exists(final):
        os.remove(final)

    paths = [os.path.join(CLIP_DIR, f) for f in files]

    cur = paths[0]
    acc_dur = get_dur(paths[0])
    for i in range(1, n):
        nxt = paths[i]
        out = os.path.join(CLIP_DIR, f'_m{i:03d}.mp4')
        off = max(acc_dur - TRANS, 0.01)
        d = merge_two(cur, nxt, out, off)
        if d is None:
            print(f'  FAILED at clip {i} ({files[i]})')
            sys.stdout.flush()
            return
        if cur.startswith(os.path.join(CLIP_DIR, '_m')):
            try: os.remove(cur)
            except: pass
        cur = out
        acc_dur = d
        if i % 5 == 0 or i == n-1:
            pct = int(i * 100 / (n - 1))
            print(f'  [{pct}%] {i}/{n-1} acc={acc_dur:.1f}s')
            sys.stdout.flush()
        gc.collect()

    os.rename(cur, final)

    d = get_dur(final)
    sz = os.path.getsize(final) / 1024 / 1024
    elapsed = time.time() - t0
    print(f'Done! {d:.1f}s, {sz:.1f}MB, {elapsed:.1f}s elapsed')
    sys.stdout.flush()

main()