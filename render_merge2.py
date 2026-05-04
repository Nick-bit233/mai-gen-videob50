import sys, os, time, sqlite3, subprocess, json, shutil, gc
sys.path.insert(0, '.')
from utils.VideoUtils import create_video_segment, remove_invalid_chars, normalize_audio_volume
from utils.PageUtils import load_style_config

FFMPEG = "ffmpeg.exe"
FFPROBE = "ffprobe.exe"
FADE_DUR = 1.0
CLIP_DIR = "b50_datas/晴蓝茶陌/videos_cpu_batches"

conn = sqlite3.connect('mai_gen_videob50.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT r.order_in_archive, r.clip_title_name, c.video_slice_start, c.video_slice_end,
           ch.video_path, ch.game_type, c.background_image_path, c.achievement_image_path, c.comment_text
    FROM records r
    LEFT JOIN configurations c ON c.chart_id = r.chart_id AND c.archive_id = r.archive_id
    LEFT JOIN charts ch ON ch.id = r.chart_id
    WHERE r.archive_id = 1 AND r.clip_title_name IN ('NewBest_9', 'PastBest_30')
    ORDER BY r.order_in_archive
""").fetchall()

style_config = load_style_config('maimai')
t0 = time.time()

for row in rows:
    idx = row['order_in_archive']
    name = row['clip_title_name']
    s = max(row['video_slice_start'] or 0, 0)
    e = max(row['video_slice_end'] or 0, s + 1)
    config = {
        'clip_title_name': name, 'game_type': row['game_type'] or 'maimai',
        'bg_image': row['background_image_path'], 'main_image': row['achievement_image_path'],
        'start': s, 'end': e, 'text': row['comment_text'],
        'video': row['video_path'], 'duration': e - s,
    }
    clean_name = remove_invalid_chars(name)
    output_file = f"{idx}_{clean_name}.mp4"
    full_path = os.path.join(CLIP_DIR, output_file)
    if os.path.exists(full_path): os.remove(full_path)
    print(f"Rendering {output_file}... slice={s}-{e}", flush=True)
    try:
        clip = create_video_segment(game_type=config['game_type'], clip_config=config, style_config=style_config, resolution=(1920, 1080))
        clip = normalize_audio_volume(clip)
        clip.write_videofile(full_path, fps=60, threads=4, preset='ultrafast', bitrate='6000k')
        clip.close(); del clip; gc.collect()
        print(f"  OK: {output_file}", flush=True)
    except Exception as ex:
        print(f"  ERROR: {ex}", flush=True)
        import traceback; traceback.print_exc()

conn.close()
print(f"Rendering done in {time.time()-t0:.1f}s", flush=True)

# Simple mode merge
print("\nSimple mode merge...", flush=True)
t1 = time.time()
files = sorted([f for f in os.listdir(CLIP_DIR) if f.endswith(".mp4") and f[0].isdigit()],
               key=lambda f: int(f.split("_")[0]))
n = len(files)
temp_dir = os.path.join(CLIP_DIR, "_simple_temp")
os.makedirs(temp_dir, exist_ok=True)

for i, f in enumerate(files):
    src = os.path.join(CLIP_DIR, f)
    r = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate", "-of", "json", src],
        capture_output=True, text=True)
    info = json.loads(r.stdout)
    s2 = info["streams"][0]
    nf = int(s2["nb_frames"])
    num, den = s2["r_frame_rate"].split("/")
    dur = nf / (float(num) / float(den))
    fos = max(dur - FADE_DUR, 0.01)
    vf = f"fade=t=in:st=0:d={FADE_DUR},fade=t=out:st={fos:.3f}:d={FADE_DUR}"
    af = f"afade=t=in:st=0:d={FADE_DUR},afade=t=out:st={fos:.3f}:d={FADE_DUR}"
    ts_path = os.path.join(temp_dir, f"{i:04d}.ts")
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-i", src, "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "fast", "-b:v", "6000k", "-maxrate", "6000k", "-bufsize", "12000k",
        "-c:a", "aac", "-b:a", "192k", "-f", "mpegts", ts_path]
    subprocess.run(cmd, capture_output=True, text=True)
    if (i+1) % 5 == 0 or i == n-1:
        print(f"  fade+ts: {i+1}/{n} ({time.time()-t1:.0f}s)", flush=True)

concat_list = os.path.join(temp_dir, "list.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    for i in range(n):
        f.write(f"file '{i:04d}.ts'\n")

output = os.path.join(CLIP_DIR, "final_output.mp4")
cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
    "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "../final_output.mp4"]
r = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
if r.returncode != 0:
    print(f"ERR: {r.stderr[:500]}", flush=True)
else:
    sz = os.path.getsize(output) / 1024 / 1024
    rp = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv", output],
        capture_output=True, text=True)
    dur = float(rp.stdout.strip().split(",")[1])
    print(f"Done! final_output.mp4: {sz:.1f}MB, {dur:.1f}s, total={time.time()-t0:.1f}s", flush=True)

try: shutil.rmtree(temp_dir)
except: pass