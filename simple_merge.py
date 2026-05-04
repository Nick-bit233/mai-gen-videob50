import subprocess, os, glob, time, json

CLIP_DIR = glob.glob("b50_datas/*/videos_cpu_batches")[0]
FFMPEG = "ffmpeg.exe"
FFPROBE = "ffprobe.exe"
FADE_DUR = 1.0  # 过渡时间（秒）

def get_clip_info(p):
    r = subprocess.run([FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames,r_frame_rate,duration",
        "-of", "json", p], capture_output=True, text=True)
    info = json.loads(r.stdout)
    s = info["streams"][0]
    nf = int(s["nb_frames"])
    num, den = s["r_frame_rate"].split("/")
    fps = float(num) / float(den)
    dur = nf / fps
    return dur, fps, nf

def main():
    t0 = time.time()
    files = sorted([f for f in os.listdir(CLIP_DIR) if f.endswith(".mp4") and f[0].isdigit()],
                   key=lambda f: int(f.split("_")[0]))
    n = len(files)
    print(f"{n} clips, fade={FADE_DUR}s", flush=True)

    temp_dir = os.path.join(CLIP_DIR, "_simple_temp")
    os.makedirs(temp_dir, exist_ok=True)

    # Step 1: Apply fade-in/out to each clip, remux to TS
    for i, f in enumerate(files):
        src = os.path.join(CLIP_DIR, f)
        dur, fps, nf = get_clip_info(src)
        
        fade_out_start = max(dur - FADE_DUR, 0.01)
        
        # Apply video fade-in + fade-out, audio fade-in + fade-out
        vf = f"fade=t=in:st=0:d={FADE_DUR},fade=t=out:st={fade_out_start:.3f}:d={FADE_DUR}"
        af = f"afade=t=in:st=0:d={FADE_DUR},afade=t=out:st={fade_out_start:.3f}:d={FADE_DUR}"
        
        ts_path = os.path.join(temp_dir, f"{i:04d}.ts")
        
        cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
            "-i", src,
            "-vf", vf, "-af", af,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-f", "mpegts", ts_path]
        
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  ERR at {f}: {r.stderr[:300]}", flush=True)
            return
        
        if (i+1) % 5 == 0 or i == n - 1:
            elapsed = time.time() - t0
            print(f"  fade+ts: {i+1}/{n} ({elapsed:.0f}s)", flush=True)
        
        # Free memory
        del r

    print(f"Fading done: {time.time()-t0:.1f}s", flush=True)

    # Step 2: Concat with TS remux
    concat_list = os.path.join(temp_dir, "list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(f"file '{os.path.join(temp_dir, f'{i:04d}.ts').replace(chr(92), '/')}'\n")

    output = os.path.join(CLIP_DIR, "final_simple.mp4")
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c", "copy", output]
    
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"Concat ERR: {r.stderr[:500]}", flush=True)
        return

    sz = os.path.getsize(output) / 1024 / 1024
    elapsed = time.time() - t0
    
    # Verify duration
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv", output],
        capture_output=True, text=True)
    dur = float(r.stdout.strip().split(",")[1]) if r.stdout.strip() else 0
    
    print(f"Done! final_simple.mp4: {sz:.1f}MB, {dur:.1f}s, {elapsed:.1f}s total", flush=True)

    # Cleanup
    import shutil
    try: shutil.rmtree(temp_dir)
    except: pass

main()