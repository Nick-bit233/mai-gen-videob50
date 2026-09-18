import os
from copy import deepcopy

THEME_COLORS = {
    "maimai": {
        "Magical": {
            "primaryColor": "#087f75",
            "backgroundColor": "#f0f8f4",
            "secondaryBackgroundColor": "#e6f3ed",
            "textColor": "#173d38"
        },
        "Prism": {
            "primaryColor": "#ff87a3",
            "backgroundColor": "#e0fff0",
            "secondaryBackgroundColor": "#ccf3ff",
            "textColor": "#003076"
        },
        "Festival": {
            "primaryColor": "#4deee2",
            "backgroundColor": "#faffca",
            "secondaryBackgroundColor": "#dfbbff",
            "textColor": "#7d308d"
        },
        "Buddies": {
            "primaryColor": "#e54271",
            "backgroundColor": "#e08b0b",
            "secondaryBackgroundColor": "#0c315b",
            "textColor": "#fbf0f4"
        },
        "Circle": {
            "primaryColor": "#002DE8",
            "backgroundColor": "#FFD7EF",
            "secondaryBackgroundColor": "#FFAEDE",
            "textColor": "#8801C2"
        }
    },
    "chunithm": {
        "Verse": {
            "primaryColor": "#1EAD85",
            "backgroundColor": "#CFF1FF",
            "secondaryBackgroundColor": "#BFFFEF",
            "textColor": "#5D2E94"
        }
    }
}

default_static_dir = "./static/assets"
DEFAULT_CONTENT_TEXT_STYLE_M = {
    "font_size": 28,
    "font_color": "#FFFFFF",
    "inline_max_chara": 26,
    "enable_stroke": True,
    "stroke_color": "#000000",
    "stroke_width": 2,
    "interline": 6.5,
    "horizontal_align": "left",
}
DEFAULT_CONTENT_TEXT_STYLE_C = {
    "font_size": 24,
    "font_color": "#FF8000",
    "inline_max_chara": 12,
    "enable_stroke": True,
    "stroke_color": "#FFFFFF",
    "stroke_width": 2,
    "interline": 6.5,
    "horizontal_align": "left",
}
DEFAULT_INTRO_TEXT_STYLE = {
    "font_size": 44,
    "font_color": "#FFFFFF",
    "inline_max_chara": 30,
    "enable_stroke": True,
    "stroke_color": "#000000",
    "stroke_width": 2,
    "interline": 6.5,
    "horizontal_align": "left",
}

DEFAULT_STYLES = {
    "maimai": [
        {
            "type": "maimai",
            "style_name": "Buddies",
            "asset_paths":{
                "score_image_assets_path": os.path.join(default_static_dir, "images"),
                "score_image_base": os.path.join(default_static_dir, "images/content_base_maimai.png"),
                "intro_video_bg": os.path.join(default_static_dir, "bg_clips/opening_bg_maimai_buddies.mp4"),
                "intro_text_bg": os.path.join(default_static_dir, "images/intro_base_maimai_buddies.png"),
                "content_bg": os.path.join(default_static_dir, "images/content_default_bg_maimai_buddies.png"),
                "intro_bgm": os.path.join(default_static_dir, "audios/intro_maimai_buddies.mp3"),
                "ui_font": os.path.join(default_static_dir, "fonts/FOT_NewRodin_Pro_EB.otf"),
                "comment_font": os.path.join(default_static_dir, "fonts/SOURCEHANSANSSC-BOLD.OTF"),
            },
            "options":{
                "override_content_default_bg": False,
                "content_use_video_bg": False
            },
            "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
            "content_text_style": DEFAULT_CONTENT_TEXT_STYLE_M
        },
        {
            "type": "maimai",
            "style_name": "Prism",
            "asset_paths": {
                "score_image_assets_path": os.path.join(default_static_dir, "images"),
                "score_image_base": os.path.join(default_static_dir, "images/content_base_maimai.png"),
                "intro_video_bg": os.path.join(default_static_dir, "bg_clips/opening_bg_maimai_prism.mp4"),
                "intro_text_bg": os.path.join(default_static_dir, "images/intro_base_maimai_prism.png"),
                "content_bg": os.path.join(default_static_dir, "images/content_default_bg_maimai_prism.png"),
                "intro_bgm": os.path.join(default_static_dir, "audios/intro_maimai_prism.mp3"),
                "ui_font": os.path.join(default_static_dir, "fonts/FOT_NewRodin_Pro_EB.otf"),
                "comment_font": os.path.join(default_static_dir, "fonts/SOURCEHANSANSSC-BOLD.OTF"),
            },
            "options": {
                "override_content_default_bg": False,
                "content_use_video_bg": False
            },
            "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
            "content_text_style": DEFAULT_CONTENT_TEXT_STYLE_M
        },
        {
            "type": "maimai",
            "style_name": "Circle",
            "asset_paths": {
                "score_image_assets_path": os.path.join(default_static_dir, "images"),
                "score_image_base": os.path.join(default_static_dir, "images/content_base_maimai.png"),
                "intro_video_bg": os.path.join(default_static_dir, "bg_clips/opening_bg_maimai_circle.mp4"),
                "intro_text_bg": os.path.join(default_static_dir, "images/intro_base_maimai_circle.png"),
                "content_bg": os.path.join(default_static_dir, "images/content_default_bg_maimai_circle.png"),
                "intro_bgm": os.path.join(default_static_dir, "audios/intro_maimai_circle.mp3"),
                "ui_font": os.path.join(default_static_dir, "fonts/FOT_NewRodin_Pro_EB.otf"),
                "comment_font": os.path.join(default_static_dir, "fonts/SOURCEHANSANSSC-BOLD.OTF"),
            },
            "options": {
                "override_content_default_bg": False,
                "content_use_video_bg": False
            },
            "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
            "content_text_style": DEFAULT_CONTENT_TEXT_STYLE_M
        },
    ],
    "chunithm": [
        {
            "type": "chunithm",
            "style_name": "Verse",
            "asset_paths": {
                "score_image_assets_path": os.path.join(default_static_dir, "images/Chunithm"),
                "score_image_base": os.path.join(default_static_dir, "images/Chunithm/content_base_chunithm_verse.png"),
                "intro_video_bg": os.path.join(default_static_dir, "bg_clips/opening_bg_chunithm_verse.mp4"),
                "intro_text_bg": os.path.join(default_static_dir, "images/Chunithm/intro_base_chunithm_verse.png"),
                "content_bg": os.path.join(default_static_dir, "images/Chunithm/content_default_bg_chunithm_verse.png"),
                "intro_bgm": os.path.join(default_static_dir, "audios/intro_chunithm_verse.mp3"),
                "ui_font": os.path.join(default_static_dir, "fonts/SweiBellLegCJKsc-Black.ttf"),
                "comment_font": os.path.join(default_static_dir, "fonts/SOURCEHANSANSSC-BOLD.OTF"),
                "content_bg_video": os.path.join(default_static_dir, "bg_clips/opening_bg_chunithm_verse.mp4"),
            },
            "options": {
                "override_content_default_bg": False,
                "content_use_video_bg": True
            },
            "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
            "content_text_style": DEFAULT_CONTENT_TEXT_STYLE_C
        },
        {
            "type": "chunithm",
            "style_name": "X-Verse",
            "asset_paths": {
                "score_image_assets_path": os.path.join(default_static_dir, "images/Chunithm"),
                "score_image_base": os.path.join(default_static_dir, "images/Chunithm/content_base_chunithm_verse.png"),
                "intro_video_bg": os.path.join(default_static_dir, "bg_clips/opening_bg_chunithm_xverse.mp4"),
                "intro_text_bg": os.path.join(default_static_dir, "images/Chunithm/intro_base_chunithm_verse.png"),
                "content_bg": os.path.join(default_static_dir, "images/Chunithm/content_default_bg_chunithm_verse.png"),
                "intro_bgm": os.path.join(default_static_dir, "audios/intro_chunithm_verse.mp3"),
                "ui_font": os.path.join(default_static_dir, "fonts/SweiBellLegCJKsc-Black.ttf"),
                "comment_font": os.path.join(default_static_dir, "fonts/SOURCEHANSANSSC-BOLD.OTF"),
                "content_bg_video": os.path.join(default_static_dir, "bg_clips/opening_bg_chunithm_verse.mp4"),
            },
            "options": {
                "override_content_default_bg": False,
                "content_use_video_bg": True
            },
            "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
            "content_text_style": DEFAULT_CONTENT_TEXT_STYLE_C
        }
    ]
}

# Keep legacy audio files available for saved styles; new presets use separate
# opening/ending tracks. CHUNITHM defaults await the user's replacement tracks.
magical_style = deepcopy(DEFAULT_STYLES["maimai"][2])
magical_style["style_name"] = "Magical"
for asset_key, relative in {
    "intro_video_bg": "bg_clips/opening_bg_maimai_magical.mp4",
    "intro_text_bg": "images/intro_base_maimai_magical.png",
    "content_bg": "images/content_default_bg_maimai_magical.png",
}.items():
    magical_style["asset_paths"][asset_key] = os.path.join(default_static_dir, relative)
DEFAULT_STYLES["maimai"].append(magical_style)

for game, styles in DEFAULT_STYLES.items():
    for style in styles:
        style["style_schema_version"] = 2
        style["base_style_name"] = style["style_name"]
        if game == "maimai":
            suffix = style["style_name"].lower()
            style["asset_paths"]["intro_bgm"] = os.path.join(default_static_dir, f"audios/opening_maimai_{suffix}.mp3")
            style["asset_paths"]["ending_bgm"] = os.path.join(default_static_dir, f"audios/ending_maimai_{suffix}.mp3")
        else:
            style["asset_paths"]["ending_bgm"] = style["asset_paths"]["intro_bgm"]
            style["options"]["chunithm_constant_display"] = "compare"
            constant_root = os.path.join(default_static_dir, "images/Chunithm/ConstantDisplay")
            style["asset_paths"].update({
                "score_image_base": os.path.join(constant_root, "content_base.png"),
                "constant_header_compare": os.path.join(constant_root, "header_compare.png"),
                "constant_header_single": os.path.join(constant_root, "header_single.png"),
                "constant_logo_cn": os.path.join(constant_root, "logo_cn_2027.png"),
                "constant_logo_latest": os.path.join(constant_root, "logo_latest_mate.png"),
            })

del magical_style, style, styles, game, suffix, asset_key, relative
