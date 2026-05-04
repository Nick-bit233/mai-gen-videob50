import sqlite3
conn = sqlite3.connect('mai_gen_videob50.db')

# 看 archive_id=1 的 50 条 records（按 order_in_archive 排序）
rows = conn.execute("""
    SELECT r.id, r.order_in_archive, r.clip_title_name, r.achievement, 
           c.video_slice_start, c.video_slice_end, c.comment_text,
           ch.song_name, ch.video_path
    FROM records r
    LEFT JOIN configurations c ON c.chart_id = r.chart_id AND c.archive_id = r.archive_id
    LEFT JOIN charts ch ON ch.id = r.chart_id
    WHERE r.archive_id = 1
    ORDER BY r.order_in_archive
""").fetchall()

# 打印第 5, 45, 46 条
for r in rows:
    if r[1] in [5, 45, 46]:
        print(f"idx={r[1]}: clip={r[2]}, ach={r[3]}, slice={r[4]}-{r[5]}")
        print(f"  song={r[7]}, video={r[8]}")
        print(f"  comment={r[6]}")
        print()

conn.close()
