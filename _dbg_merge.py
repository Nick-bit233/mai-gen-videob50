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
                fr = float(num) / float(den)
                return nf / fr
            except Exception as e:
                print(f"  get_dur parse err: {e} [{line}]")
    # fallback
    r2 = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv", p],
        capture_output=True, text=True)
    for line in r2.stdout.strip().split(chr(10)):
        if line.startswith("format"): return float(line.split(",")[1])
    return 0

files = sorted([f for f in os.listdir(CLIP_DIR) if f.endswith(".mp4") and f[0].isdigit()], key=lambda f: int(f.split("_")[0]))
f0 = os.path.join(CLIP_DIR, files[0])
f1 = os.path.join(CLIP_DIR, files[1])
f2 = os.path.join(CLIP_DIR, files[2])

d0 = get_dur(f0)
d1 = get_dur(f1)
d2 = get_dur(f2)
print(f"Sources: {d0:.3f}, {d1:.3f}, {d2:.3f}")

# Step 1
off1 = d0 - TRANS
print(f"\nStep 1: off={off1:.3f}")
flt = (f"[0:v]fps={FPS},format=yuv420p[v0];"
       f"[1:v]fps={FPS},format=yuv420p[v1];"
       f"[v0][v1]xfade=transition=fade:duration={TRANS}:offset={off1:.3f}[vout];"
       f"[0:a][1:a]concat=n=2:v=0:a=1[aout]")
out1 = os.path.join(CLIP_DIR, "_dbg1.mp4")
cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
    "-i", f0, "-i", f1, "-filter_complex", flt,
    "-map", "[vout]", "-map", "[aout]",
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
    "-shortest", out1]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(f"  ERR: {r.stderr[:400]}")
else:
    # Full ffprobe on output
    r1 = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate,duration",
        "-of", "csv", out1], capture_output=True, text=True)
    r2 = subprocess.run([FFPROBE, "-v", "error",
        "-show_entries", "format=duration,nb_frames",
        "-of", "csv", out1], capture_output=True, text=True)
    d_out = get_dur(out1)
    print(f"  stream: {r1.stdout.strip()}")
    print(f"  format: {r2.stdout.strip()}")
    print(f"  get_dur: {d_out:.3f}s (expected {d0+d1-TRANS:.3f}s)")

    # Step 2
    off2 = d_out - TRANS
    print(f"\nStep 2: off={off2:.3f}")
    flt2 = (f"[0:v]fps={FPS},format=yuv420p[v0];"
            f"[1:v]fps={FPS},format=yuv420p[v1];"
            f"[v0][v1]xfade=transition=fade:duration={TRANS}:offset={off2:.3f}[vout];"
            f"[0:a][1:a]concat=n=2:v=0:a=1[aout]")
    out2 = os.path.join(CLIP_DIR, "_dbg2.mp4")
    cmd2 = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", out1, "-i", f2, "-filter_complex", flt2,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-shortest", out2]
    r = subprocess.run(cmd2, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ERR: {r.stderr[:400]}")
    else:
        r1 = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=nb_frames,r_frame_rate,duration",
            "-of", "csv", out2], capture_output=True, text=True)
        r2 = subprocess.run([FFPROBE, "-v", "error",
            "-show_entries", "format=duration,nb_frames",
            "-of", "csv", out2], capture_output=True, text=True)
        d_out2 = get_dur(out2)
        expected = d0+d1+d2-2*TRANS
        print(f"  stream: {r1.stdout.strip()}")
        print(f"  format: {r2.stdout.strip()}")
        print(f"  get_dur: {d_out2:.3f}s (expected {expected:.3f}s)")

    os.remove(out1)
    if os.path.exists(out2): os.remove(out2)

print("Done")