import subprocess, os, glob, time, json

CLIP_DIR = glob.glob("b50_datas/*/videos_cpu_batches")[0]
FFMPEG = "ffmpeg.exe"
FFPROBE = "ffprobe.exe"
FADE_DUR = 1.0

files = sorted([f for f in os.listdir(CLIP_DIR) if f.endswith(".mp4") and f[0].isdigit()],
               key=lambda f: int(f.split("_")[0]))
n = len(files)
print(f"{n} clips, xfade fade transition", flush=True)

# 用简单模式已经烘焙好 fade 的片段（final_simple.mp4 不行，要用原始片段+FFmpeg fade）
# 直接从原始片段用 FFmpeg fade 滤镜 + xfade 合并
# 但更好的方案：先对每个片段用 FFmpeg 加 fade，然后两两 xfade

# 方案：用 FFmpeg 在一次 filter_complex 中完成
# 对于 2 个片段: [0:v]fade=in:...[v0];[1:v]fade=out:...[v1];[v0][v1]xfade=fade:d=1:offset=X[v]
# 但这太复杂了

# 更简单的方案：对每个片段先加 fade（音视频），然后两两 xfade
# 这跟我的 acrossfade 方案一样，只是用 fade-in/out 而不是 xfade 重叠

t0 = time.time()

def get_dur_fps(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate",
        "-of", "json", p], capture_output=True, text=True)
    info = json.loads(r.stdout)
    s = info["streams"][0]
    nf = int(s["nb_frames"])
    num, den = s["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    return nf / fps, fps

def get_audio_dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=duration",
        "-of", "csv", p], capture_output=True, text=True)
    for line in r.stdout.strip().split(chr(10)):
        parts = line.split(",")
        if len(parts) >= 2 and parts[0] == "stream":
            try: return float(parts[1])
            except: pass
    return 0

# Step 1: 对每个片段加 FadeIn/FadeOut（视频+音频）
temp_dir = os.path.join(CLIP_DIR, "_xfade_temp")
os.makedirs(temp_dir, exist_ok=True)

print("Step 1: Adding fade to clips...", flush=True)
faded_paths = []
for i, f in enumerate(files):
    src = os.path.join(CLIP_DIR, f)
    dur, fps = get_dur_fps(src)
    fade_out_start = max(dur - FADE_DUR, 0.01)
    
    out = os.path.join(temp_dir, f"{i:04d}.mp4")
    vf = f"fade=t=in:st=0:d={FADE_DUR},fade=t=out:st={fade_out_start:.3f}:d={FADE_DUR}"
    af = f"afade=t=in:st=0:d={FADE_DUR},afade=t=out:st={fade_out_start:.3f}:d={FADE_DUR}"
    
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", src, "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", out]
    subprocess.run(cmd, capture_output=True, text=True)
    faded_paths.append(out)
    
    if (i+1) % 5 == 0:
        print(f"  faded {i+1}/{n} ({time.time()-t0:.0f}s)", flush=True)

print(f"Fade done: {time.time()-t0:.1f}s", flush=True)

# Step 2: 两两 xfade 合并（与 ffmpeg-concat fade 效果相同）
# 每个片段已有首尾 fade，xfade 时 offset 设在两片段重叠的黑色区域
# 用 xfade + acrossfade 保持音视频同步

cur = faded_paths[0]
cur_dur, _ = get_dur_fps(cur)

for i in range(1, n):
    nxt = faded_paths[i]
    nxt_dur, _ = get_dur_fps(nxt)
    
    # offset: 在当前片段的 fade-out 区域开始 xfade
    # 当前片段总时长 cur_dur，fade-out 从 cur_dur-FADE_DUR 开始
    # xfade 从 cur_dur - FADE_DUR 开始（正好在 fade-out 区域）
    off = max(cur_dur - FADE_DUR, 0.01)
    
    out = os.path.join(temp_dir, f"_m{i}.mp4")
    flt = (f"[0:v]fps=60,format=yuv420p[v0];"
           f"[1:v]fps=60,format=yuv420p[v1];"
           f"[v0][v1]xfade=transition=fade:duration={FADE_DUR}:offset={off:.3f}[vout];"
           f"[0:a][1:a]acrossfade=d={FADE_DUR}:c1=tri:c2=tri[aout]")
    
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", cur, "-i", nxt, "-filter_complex", flt,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-shortest", out]
    
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERR at step {i}: {r.stderr[:300]}", flush=True)
        break
    
    # Cleanup previous
    if cur != faded_paths[0]:
        try: os.remove(cur)
        except: pass
    
    cur = out
    cur_dur, _ = get_dur_fps(cur)
    
    if i % 5 == 0 or i == n - 1:
        print(f"  xfade {i}/{n-1} dur={cur_dur:.1f}s ({time.time()-t0:.0f}s)", flush=True)

# Move to final output
final = os.path.join(CLIP_DIR, "final_xfade_fade.mp4")
os.rename(cur, final)

sz = os.path.getsize(final) / 1024 / 1024
print(f"Done! final_xfade_fade.mp4: {sz:.1f}MB, {cur_dur:.1f}s, {time.time()-t0:.1f}s", flush=True)

# Cleanup
import shutil
try: shutil.rmtree(temp_dir)
except: pass