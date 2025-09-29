import os

THEME_COLORS = {
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
}

default_static_dir = "./static/assets"
DEFAULT_CONENT_TEXT_STYLE = {
    "font_size": 28,
    "font_color": "#FFFFFF",
    "inline_max_chara": 24,
    "enable_stroke": True,
    "stroke_color": "#000000",
    "stroke_width": 2,
    "interline": 6.5,
    "horizontal_align": "left",
}
DEFAULT_INTRO_TEXT_STYLE = {
    "font_size": 44,
    "font_color": "#FFFFFF",
    "inline_max_chara": 26,
    "enable_stroke": True,
    "stroke_color": "#000000",
    "stroke_width": 2,
    "interline": 6.5,
    "horizontal_align": "left",
}

DEFAULT_STYLES = {
    "Buddies": {
        "type": "maimai",
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
        },
        "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
        "content_text_style": DEFAULT_CONENT_TEXT_STYLE

    },
    "Prism": {
        "type": "maimai",
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
        },
        "intro_text_style": DEFAULT_INTRO_TEXT_STYLE,
        "content_text_style": DEFAULT_CONENT_TEXT_STYLE
    }
}