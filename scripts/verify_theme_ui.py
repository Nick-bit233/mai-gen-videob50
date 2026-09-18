"""Exercise theme pages in a fresh application copy with synthetic user data."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]


def element(items, label):
    return next(item for item in items if item.label == label)


def healthy(page):
    assert not page.exception, page.exception


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    if not root.is_relative_to(SOURCE / "test_output"):
        parser.error("UI acceptance copies must be inside this repository's test_output directory")
    root.mkdir(parents=True, exist_ok=False)
    (root / ".theme-acceptance-workspace").touch()
    for name in ("utils", "db_utils", "st_pages"):
        shutil.copytree(SOURCE / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(SOURCE / "static/assets", root / "static/assets", ignore=shutil.ignore_patterns("jackets", "custom_jackets"))
    (root / "global_config.yaml").write_text(json.dumps({
        "VIDEO_RES": [640, 360], "ONLY_GENERATE_CLIPS": False, "VIDEO_FPS": 30,
        "VIDEO_BITRATE": 1500, "VIDEO_TRANS_ENABLE": True, "VIDEO_TRANS_TIME": 1.0,
        "USE_GPU_ACCEL": False, "TAICHI_BACKEND": "auto"}), encoding="utf-8")
    (root / "music_metadata").mkdir()
    (root / "music_metadata/chuni_fusion_data.json").write_text("[]")
    os.chdir(root)
    sys.path.insert(0, str(root))
    from streamlit.testing.v1 import AppTest
    from utils.style_config import read_style, write_style, preset_style
    from db_utils.DatabaseDataHandler import DatabaseDataHandler
    import utils.VideoUtils as videos
    import utils.PageUtils as page_utils
    from utils.themes import THEME_COLORS

    page = AppTest.from_file(str(root / "st_pages/Custom_Video_Style_Config.py"))
    page.session_state["game_type"] = "maimai"
    page.run(timeout=60)
    healthy(page)
    element(page.radio, "视频样式预设").set_value("Magical").run(timeout=60)
    element(page.button, "应用预设").click().run(timeout=60)
    healthy(page)
    assert read_style("maimai")["style_name"] == "Magical"
    assert "ending_maimai_magical" in read_style("maimai")["asset_paths"]["ending_bgm"]
    element(page.number_input, "片头片尾文本字体大小").set_value(55).run(timeout=60)
    element(page.button, "保存自定义样式").click().run(timeout=60)
    healthy(page)
    assert read_style("maimai")["intro_text_style"]["font_size"] == 55
    # Applying another preset must reset widget values, not revive old custom values.
    element(page.radio, "视频样式预设").set_value("Prism").run(timeout=60)
    element(page.button, "应用预设").click().run(timeout=60)
    healthy(page)
    assert element(page.number_input, "片头片尾文本字体大小").value == 44
    page.session_state["game_type"] = "chunithm"
    page.run(timeout=60)
    healthy(page)
    element(page.radio, "定数展示选项").set_value("latest").run(timeout=60)
    element(page.button, "保存自定义样式").click().run(timeout=60)
    element(page.radio, "视频样式预设").set_value("X-Verse").run(timeout=60)
    element(page.button, "应用预设").click().run(timeout=60)
    healthy(page)
    assert read_style("chunithm")["options"]["chunithm_constant_display"] == "latest"
    element(page.button, "生成预览图").click().run(timeout=60)
    healthy(page)
    assert not page.error, page.error

    handler = DatabaseDataHandler(str(root / "mai_gen_videob50.db"))
    archive_id, name = handler.create_new_archive("theme-test", game_type="chunithm")
    with handler.db.get_connection() as conn:
        conn.execute("INSERT INTO charts (id, song_id, game_type, chart_type, level_index, difficulty, song_name, artist) VALUES (1, '1', 'chunithm', 0, 3, '14.4', 'Theme test', 'Test')")
        conn.execute("INSERT INTO records (archive_id, chart_id, order_in_archive, achievement, chuni_rating, play_count, fc_status, fs_status) VALUES (?, 1, 0, 1009000, 16.55, 5, 'aj', 'fc')", (archive_id,))
        conn.commit()
    state = dict(game_type="chunithm", username="theme-test", archive_name=name, archive_id=archive_id)
    image_page = AppTest.from_file(str(root / "st_pages/Generate_Pic_Resources.py"))
    for key, value in state.items():
        image_page.session_state[key] = value
    image_page.run(timeout=60)
    healthy(image_page)
    # Toggle away and back to detect stale Streamlit widget state.
    for mode in ("cn", "compare", "latest", "cn"):
        element(image_page.radio, "定数展示选项").set_value(mode).run(timeout=60)
        healthy(image_page)
        assert read_style("chunithm")["options"]["chunithm_constant_display"] == mode
    element(image_page.button, "🎨 开始生成成绩背景图片").click().run(timeout=60)
    healthy(image_page)
    assert not image_page.error, image_page.error
    with handler.db.get_connection() as conn:
        image = conn.execute("SELECT achievement_image_path FROM configurations WHERE archive_id=?", (archive_id,)).fetchone()[0]
    assert Path(image).is_file() and Path(image + ".theme.json").is_file()

    composite = AppTest.from_file(str(root / "st_pages/Composite_Videos.py"))
    for key, value in state.items():
        composite.session_state[key] = value
    configs = ([{"clip_title_name": "fixture", "main_image": image}], [{"duration": 1}], [{"duration": 1}])
    with patch.object(DatabaseDataHandler, "load_full_config_for_composite_video", return_value=configs), patch.object(videos, "render_complete_full_video", return_value={"status": "error", "info": "injected render failure"}) as renderer:
        composite.run(timeout=60)
        element(composite.button, "开始生成视频").click().run(timeout=60)
        healthy(composite)
        assert renderer.call_count == 1
        assert any("injected render failure" in item.value for item in composite.error)
        assert not any("完整视频生成结束" in item.value for item in composite.success)
        changed = read_style("chunithm")
        changed["options"]["chunithm_constant_display"] = "latest"
        write_style("chunithm", changed)
        composite.run(timeout=60)
        element(composite.button, "开始生成视频").click().run(timeout=60)
        healthy(composite)
        assert renderer.call_count == 1
        assert any("重新生成成绩背景图片" in item.value for item in composite.error)
    (root / ".streamlit").mkdir(exist_ok=True)
    page_utils.change_theme(THEME_COLORS["maimai"]["Magical"])
    assert "#087f75" in (root / ".streamlit/config.toml").read_text()
    report = {"preset_and_custom_save": "passed", "game_switch_and_widget_reset": "passed",
              "three_modes_and_image_batch": "passed", "stale_image_preflight": "passed",
              "render_failure_not_success": "passed", "magical_palette_save": "passed"}
    (root / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
