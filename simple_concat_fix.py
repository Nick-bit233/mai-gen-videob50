import subprocess, os, glob

CLIP_DIR = glob.glob("b50_datas/*/videos_cpu_batches")[0]
FFMPEG = "ffmpeg.exe"
FFPROBE = "ffprobe.exe"
temp_dir = os.path.join(CLIP_DIR, "_simple_temp")

# 写 list 文件用相对路径（相对 temp_dir）
n = len([f for f in os.listdir(temp_dir) if f.endswith(".ts")])
concat_list = os.path.join(temp_dir, "list.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    for i in range(n):
        f.write(f"file '{i:04d}.ts'\n")

output = os.path.join(CLIP_DIR, "final_simple.mp4")
# 从 temp_dir 运行 concat
cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
    "-f", "concat", "-safe", "0", "-i", "list.txt",
    "-c", "copy", "../final_simple.mp4"]
r = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
if r.returncode != 0:
    print(f"ERR: {r.stderr[:500]}", flush=True)
else:
    sz = os.path.getsize(output) / 1024 / 1024
    rp = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv", output],
        capture_output=True, text=True)
    dur = float(rp.stdout.strip().split(",")[1])
    print(f"Done! final_simple.mp4: {sz:.1f}MB, {dur:.1f}s", flush=True)

# Cleanup
import shutil
try: shutil.rmtree(temp_dir)
except: pass