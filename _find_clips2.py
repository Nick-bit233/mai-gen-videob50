import sqlite3
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
for r in rows:
    print(f"idx={r['order_in_archive']}: {r['clip_title_name']}, slice={r['video_slice_start']}-{r['video_slice_end']}")
conn.close()