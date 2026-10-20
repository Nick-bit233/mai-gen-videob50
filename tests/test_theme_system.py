"""Theme compatibility, independent audio and CHUNITHM display regressions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.style_config import (normalize_style, read_style, write_style, preset_style,
                                resolve_bgm, constant_mode)


class AdvancedFrameTests(unittest.TestCase):
    def test_advanced_frame_preserves_alpha_and_uses_orange_palette(self):
        import colorsys
        from PIL import Image
        directory = Path(__file__).resolve().parents[1] / 'static/assets/images/Chunithm/Frames'
        with Image.open(directory/'1.png') as advanced, Image.open(directory/'2.png') as expert:
            self.assertEqual(advanced.size, (1311, 780))
            self.assertEqual(advanced.mode, 'RGBA')
            self.assertEqual(advanced.getchannel('A').tobytes(), expert.getchannel('A').tobytes())
            visible = [pixel for pixel in advanced.getdata() if pixel[3] > 128]
            orange = [p for p in visible if p[0] > p[1] > p[2] and
                      20 <= colorsys.rgb_to_hsv(*(v/255 for v in p[:3]))[0]*360 <= 40]
            self.assertGreater(len(orange)/len(visible), 0.95)
            self.assertEqual(advanced.getpixel((700, 400))[3], 0)

    def test_advanced_renders_in_all_chunithm_presets_and_display_modes(self):
        from utils.ImageUtils import generate_single_image
        record = dict(title='ADVANCED 验收', artist='Test', level_index=1,
                      ds_cur=7.5, ds_next=7.7, ds_cn=7.5, ds_latest=7.7,
                      score=1009000, ra=9.65, combo_type='aj', chain_type='fc', play_count=1)
        with tempfile.TemporaryDirectory() as directory:
            for name in ('Verse', 'X-Verse', 'MATE'):
                for mode in ('cn', 'latest', 'compare'):
                    with self.subTest(preset=name, mode=mode):
                        style = preset_style('chunithm', name)
                        style['options']['chunithm_constant_display'] = mode
                        result = generate_single_image('chunithm', style, record,
                            str(Path(directory)/f'{name}-{mode}.png'), 'Best 1')
                        self.assertEqual(result.size, (1920, 1080))
                        r,g,b,_ = result.convert('RGBA').getpixel((400,55))
                        self.assertGreater(r,g)
                        self.assertGreater(g,b)
                        result.close()


class StyleTests(unittest.TestCase):
    def test_legacy_custom_keeps_audio_and_other_game(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "styles.json"
            legacy = {"style_name": "Custom", "asset_paths": {"intro_bgm": "my music.wav"}}
            config.write_text(json.dumps({"maimai": legacy, "chunithm": {"marker": 1}}))
            original = config.read_text()
            style = read_style("maimai", config)
            self.assertEqual(config.read_text(), original)
            self.assertEqual(style["asset_paths"]["ending_bgm"], "my music.wav")
            self.assertIsNone(style["base_style_name"])
            write_style("maimai", style, config)
            self.assertEqual(json.loads(config.read_text())["chunithm"], {"marker": 1})
            self.assertEqual(read_style("maimai", config), style)

    def test_new_presets_have_real_assets_and_isolated_mutation(self):
        for game, names in (("maimai", ("Buddies", "Prism", "Circle", "Magical")),
                            ("chunithm", ("Verse", "X-Verse", "MATE"))):
            for name in names:
                style = preset_style(game, name)
                for key, value in style["asset_paths"].items():
                    self.assertTrue(Path(value).exists(), (name, key, value))
                self.assertNotEqual(resolve_bgm(style, "intro"), resolve_bgm(style, "ending"))
                style["options"]["dummy"] = True
                self.assertNotIn("dummy", preset_style(game, name)["options"])

    def test_mate_and_legacy_builtin_audio_migration_keep_custom_paths(self):
        mate = preset_style('chunithm', 'MATE')
        verse = preset_style('chunithm', 'Verse')
        self.assertEqual(mate['asset_paths']['score_image_base'], verse['asset_paths']['score_image_base'])
        self.assertIn('opening_bg_chunithm_mate.mp4', mate['asset_paths']['intro_video_bg'])
        self.assertEqual(mate['asset_paths']['intro_video_bg'], mate['asset_paths']['content_bg_video'])
        legacy = {'style_name': 'X-Verse', 'asset_paths': {'intro_bgm': './static/assets/audios/intro_chunithm_verse.mp3'}}
        migrated = normalize_style(legacy, 'chunithm')
        self.assertTrue(resolve_bgm(migrated, 'intro').endswith('opening_chunithm_verse.mp3'))
        self.assertTrue(resolve_bgm(migrated, 'ending').endswith('ending_chunithm_verse.mp3'))
        self.assertNotIn('ending_bgm', legacy['asset_paths'])
        custom = {'style_name': 'Custom', 'base_style_name': 'MATE',
                  'asset_paths': {'intro_bgm': 'user-opening.wav', 'ending_bgm': 'user-ending.wav'}}
        retained = normalize_style(custom, 'chunithm')
        self.assertEqual(retained['asset_paths']['intro_bgm'], 'user-opening.wav')
        self.assertEqual(retained['asset_paths']['ending_bgm'], 'user-ending.wav')

    def test_bad_mode_and_missing_explicit_ending_fail(self):
        with self.assertRaises(ValueError):
            normalize_style({"options": {"chunithm_constant_display": "bad"}}, "chunithm")
        self.assertEqual(constant_mode({}), "compare")
        style = preset_style("maimai")
        style["asset_paths"]["ending_bgm"] = "missing.wav"
        with self.assertRaises(FileNotFoundError):
            resolve_bgm(style, "ending")
        with self.assertRaises(ValueError):
            resolve_bgm(style, "info")

    def test_upload_failure_does_not_publish_or_replace(self):
        from utils.bgm_upload import save_bgm_upload
        with tempfile.TemporaryDirectory() as directory:
            with patch("utils.bgm_upload.validate_audio", side_effect=ValueError("bad audio")):
                with self.assertRaises(ValueError):
                    save_bgm_upload("test.wav", b"bad", directory, "maimai", "ending")
            self.assertEqual(list(Path(directory).rglob("*.wav")), [])
            with patch("utils.bgm_upload.validate_audio", return_value=1):
                first = save_bgm_upload("same.wav", b"first", directory, "maimai", "intro")
                second = save_bgm_upload("same.wav", b"second", directory, "maimai", "intro")
                ending = save_bgm_upload("same.wav", b"ending", directory, "maimai", "ending")
            self.assertEqual(len({first, second, ending}), 3)
            self.assertEqual(Path(first).read_bytes(), b"first")


class ConstantTests(unittest.TestCase):
    def test_single_modes_never_fall_back_and_do_not_mutate_rating(self):
        from utils.chunithm_display import archive_constants, display_constants
        meta = {"charts_info": [{"difficulty": 3, "level_value_cn": None, "level_value_latest": 14.5}]}
        record = {**archive_constants(meta, 3, 12.0), "ra": 16.1, "score": 1009000}
        self.assertEqual(record["ds_cur"], 14.5)  # legacy comparison fallback
        original = copy.deepcopy(record)
        style = preset_style("chunithm")
        style["options"]["chunithm_constant_display"] = "cn"
        display = display_constants(record, style)
        self.assertIsNone(display["level"])
        self.assertEqual(display["columns"][0][1], "--")
        style["options"]["chunithm_constant_display"] = "latest"
        self.assertEqual(display_constants(record, style)["level"], 14.5)
        self.assertEqual(record, original)

    def test_compare_arrows_and_invalid_values(self):
        from utils.chunithm_display import display_constants
        style = preset_style("chunithm")
        for current, latest, expected in [(14.4, 14.5, "14.5↑"), (14.5, 14.4, "14.4↓"),
                                          (14.5, 14.5, "14.5→"), (None, 14.5, "14.5"), (14.5, None, "--")]:
            self.assertEqual(display_constants({"ds_cur": current, "ds_next": latest}, style)["columns"][1][1], expected)
        style["options"]["chunithm_constant_display"] = "cn"
        for value in (None, 0, -1, "--", "?", "nan", float("inf"), True):
            self.assertEqual(display_constants({"ds_cn": value, "ds_latest": 14.5}, style)["columns"][0][1], "--")

    def test_only_matching_chart_and_no_unversioned_custom_fallback(self):
        from utils.chunithm_display import archive_constants
        record = archive_constants({"charts_info": [{"difficulty": 2, "level_value_cn": 15}]}, 3, "14.9")
        self.assertEqual(record, {"ds_cur": "14.9", "ds_next": None, "ds_cn": None, "ds_latest": None})


class RecipeTests(unittest.TestCase):
    def test_bgm_changes_only_the_affected_section(self):
        from utils.theme_artifacts import clip_recipe, image_recipe
        style = preset_style("maimai", "Magical")
        def recipe(section):
            return clip_recipe("maimai", style, {"duration": 1, "text": ""}, section, (640, 360), 30, "1000k", [False, 0], "cpu")
        original = {section: recipe(section) for section in ("intro", "ending", "content")}
        image = image_recipe("maimai", style)
        style["asset_paths"]["ending_bgm"] = preset_style("maimai", "Circle")["asset_paths"]["ending_bgm"]
        self.assertNotEqual(recipe("ending"), original["ending"])
        self.assertEqual(recipe("intro"), original["intro"])
        self.assertEqual(recipe("content"), original["content"])
        self.assertEqual(image_recipe("maimai", style), image)

    def test_image_mode_change_is_rejected_even_after_reopening(self):
        from utils.theme_artifacts import record_image_recipe, validate_image_style
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.png"
            image.touch()
            style = preset_style("chunithm")
            record_image_recipe(image, "chunithm", style)
            validate_image_style(image, "chunithm", style, True)
            other = copy.deepcopy(style)
            other["options"]["chunithm_constant_display"] = "cn"
            with self.assertRaises(ValueError):
                validate_image_style(image, "chunithm", other, True)
            missing = Path(directory) / "legacy.png"
            missing.touch()
            with self.assertRaises(ValueError):
                validate_image_style(missing, "chunithm", style, True)

    def test_partial_database_batch_rolls_back(self):
        from db_utils.DatabaseDataHandler import DatabaseDataHandler
        with tempfile.TemporaryDirectory() as directory:
            handler = DatabaseDataHandler(str(Path(directory) / "test.db"))
            with handler.db.get_connection() as conn:
                conn.execute("INSERT INTO users (id, username) VALUES (1, 'test')")
                conn.execute("INSERT INTO archives (id, user_id, archive_name) VALUES (1, 1, 'test')")
                conn.execute("INSERT INTO charts (id, song_id, game_type, chart_type, level_index) VALUES (1, '1', 'chunithm', 0, 3)")
                conn.execute("INSERT INTO records (archive_id, chart_id, achievement, order_in_archive) VALUES (1, 1, 1009000, 0)")
                conn.execute("INSERT INTO configurations (archive_id, chart_id, achievement_image_path, comment_text) VALUES (1, 1, 'old.png', 'keep comment')")
                conn.commit()
            with self.assertRaises(ValueError):
                handler.update_image_configs_batch(1, [(1, {"achievement_image_path": "new.png"}), (999, {"achievement_image_path": "bad.png"})])
            with handler.db.get_connection() as conn:
                row = conn.execute("SELECT achievement_image_path, comment_text FROM configurations").fetchone()
                self.assertEqual(tuple(row), ("old.png", "keep comment"))
            handler.update_image_configs_batch(1, [(1, {"achievement_image_path": "new.png"})])
            with handler.db.get_connection() as conn:
                self.assertEqual(tuple(conn.execute("SELECT achievement_image_path, comment_text FROM configurations").fetchone()), ("new.png", "keep comment"))


class ImageLayoutTests(unittest.TestCase):
    def test_missing_single_level_uses_unknown_label_instead_of_zero(self):
        from utils.ImageUtils import ChuniImageGenerater
        generator = ChuniImageGenerater(preset_style("chunithm"))
        with patch.object(generator, "TextDraw", wraps=generator.TextDraw) as draw:
            generator.LevelLoader("--")
            self.assertEqual(draw.call_args.args[1], "--")

    def test_modes_change_only_constants_and_level(self):
        from PIL import ImageChops
        from utils.ImageUtils import ChuniImageGenerater
        record = dict(title="Layout test", artist="Test", level_index=3, ds_cur=14.4, ds_next=14.6,
                      ds_cn=14.4, ds_latest=14.6, score=1009000, ra=16.55, combo_type="aj", chain_type="fc")
        for theme in ("Verse", "X-Verse", "MATE"):
            images = {}
            for mode in ("cn", "latest", "compare"):
                style = preset_style("chunithm", theme)
                style["options"]["chunithm_constant_display"] = mode
                images[mode] = ChuniImageGenerater(style).GenerateOneAchievement(record).convert("RGB")
                self.assertEqual(images[mode].size, (1920, 1080))
            for mode in ("cn", "latest"):
                # Title, score, rating and gameplay frame stay exactly unchanged.
                for box in ((0, 0, 1448, 830), (224, 830, 1448, 1080)):
                    self.assertIsNone(ImageChops.difference(images[mode].crop(box), images["compare"].crop(box)).getbbox())
            self.assertIsNotNone(ImageChops.difference(images["cn"].crop((102,884,210,972)),
                                                     images["latest"].crop((102,884,210,972))).getbbox())
            style["options"]["chunithm_constant_display"] = "cn"
            missing = ChuniImageGenerater(style).GenerateOneAchievement(dict(record, ds_cn=None))
            self.assertEqual(missing.size, (1920, 1080))


class RenderPublicationTests(unittest.TestCase):
    def test_failed_cpu_clip_keeps_previous_output(self):
        from utils.VideoUtils import render_all_video_clips
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            previous = Path(directory) / "0_INTRO.mp4"
            previous.write_bytes(b"previous finished video")
            clip = Mock()
            def fail(path, **kwargs):
                Path(path).write_bytes(b"unfinished video")
                raise RuntimeError("injected writer failure")
            clip.write_videofile.side_effect = fail
            with patch("utils.VideoUtils.create_info_segment", return_value=clip), patch("utils.VideoUtils.normalize_audio_volume", side_effect=lambda value: value):
                with self.assertRaisesRegex(RuntimeError, "injected writer"):
                    render_all_video_clips("maimai", preset_style("maimai"), [], directory,
                        video_res=(640, 360), video_bitrate="1000k", intro_configs=[{"duration": 1, "text": ""}], auto_add_transition=False, use_gpu_accel=False)
            self.assertEqual(previous.read_bytes(), b"previous finished video")
            self.assertEqual(list(Path(directory).glob(".render-*")), [])
            self.assertFalse((Path(directory) / "clip_order.json").exists())

    def test_completed_clip_order_excludes_leftover_segments(self):
        from utils.theme_artifacts import record_clip_order, ordered_clip_files
        with tempfile.TemporaryDirectory() as directory:
            for name in ("0_INTRO.mp4", "1_ENDING.mp4", "1_OldChart.mp4", "20_OldEnding.mp4"):
                (Path(directory) / name).touch()
            record_clip_order(directory, ["0_INTRO.mp4", "1_ENDING.mp4"])
            self.assertEqual(ordered_clip_files(directory), ["0_INTRO.mp4", "1_ENDING.mp4"])
            (Path(directory) / "1_ENDING.mp4").unlink()
            with self.assertRaises(ValueError):
                ordered_clip_files(directory)


if __name__ == "__main__":
    unittest.main()
