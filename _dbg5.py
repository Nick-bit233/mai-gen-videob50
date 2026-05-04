import subprocess, os, glob

CLIP_DIR = glob.glob("b50_datas/*/videos_cpu_batches")[0]
FFMPEG = "ffmpeg.exe"
FFPROBE = "ffprobe.exe"
TRANS = 1.5
FPS = 60

def get_dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate",
        "-of", "csv", p], capture_output=True, text=True)
    for line in r.stdout.strip().split(chr(10)):
        parts = line.split(",")
        if len(parts) >= 3 and parts[0] == "stream":
            try:
                nf = int(parts[2])
                num, den = parts[1].split("/")
                return nf / (float(num) / float(den))
            except: pass
    r2 = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv", p],
        capture_output=True, text=True)
    for line in r2.stdout.strip().split(chr(10)):
        if line.startswith("format"): return float(line.split(",")[1])
    return 0

def merge(a, b, out, off):
    flt = (f"[0:v]fps={FPS},format=yuv420p[v0];"
           f"[1:v]fps={FPS},format=yuv420p[v1];"
           f"[v0][v1]xfade=transition=fade:duration={TRANS}:offset={off:.3f}[vout];"
           f"[0:a][1:a]concat=n=2:v=0:a=1[aout]")
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", a, "-i", b, "-filter_complex", flt,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERR: {r.stderr[:300]}")
        return None
    return get_dur(out)

files = sorted([f for f in os.listdir(CLIP_DIR) if f.endswith(".mp4") and f[0].isdigit()], key=lambda f: int(f.split("_")[0]))

# 5 段顺序合并
paths = [os.path.join(CLIP_DIR, f) for f in files[:5]]
cur = paths[0]
acc = get_dur(cur)
expected_acc = get_dur(cur)

for i in range(1, 5):
    off = max(acc - TRANS, 0.01)
    out = os.path.join(CLIP_DIR, f"_seq{i}.mp4")
    d_clip = get_dur(paths[i])
    d = merge(cur, paths[i], out, off)
    expected_acc += d_clip - TRANS
    print(f"Step {i}: off={off:.3f}, clip_dur={d_clip:.3f}, output={d:.3f}s, expected_acc={expected_acc:.3f}s")
    if cur.startswith(os.path.join(CLIP_DIR, "_seq")):
        try: os.remove(cur)
        except: pass
    cur = out
    acc = d

# Cleanup
try: os.remove(cur)
except: pass
print("Done")