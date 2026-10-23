import streamlit as st
import streamlit.components.v1 as components
import os
import json
import pyperclip
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from utils.themes import DEFAULT_STYLES
from utils.style_config import read_style, write_style, preset_style, RESET_STYLES, CONSTANT_MODES, constant_mode
from utils.bgm_upload import save_bgm_upload
from uuid import uuid4
from utils.PageUtils import read_global_config, get_game_type_text, DEFAULT_STYLE_CONFIG_FILE_PATH
from utils.ImageUtils import generate_single_image
from utils.VideoUtils import get_video_preview_frame

DEFAULT_STYLE_KEY = "Prism"
video_style_config_path = DEFAULT_STYLE_CONFIG_FILE_PATH

# 配置素材文件夹
default_static_dir = "./static/assets"
user_static_dir = "./static/user"
temp_static_dir = "./static/thumbnails"
os.makedirs(user_static_dir, exist_ok=True)
os.makedirs(temp_static_dir, exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "backgrounds"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "audios"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "fonts"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "bg_clips"), exist_ok=True)


G_config = read_global_config()  # 读取全局配置
G_type = st.session_state.get('game_type', 'maimai')  # 当前游戏类型

_kop7 = """kop7th规则怪谈
1️⃣ 不要在比赛前AP白xx，否则会被天意侵蚀心智❌
2️⃣ 当你站在右侧机位前时，注意每一条你过去可能忽略的星星🔎🌟
3️⃣ 预选前三不比预选倒一和lcq强🤷‍♂️🎲
4️⃣ 注意前三条规则，并将该比赛当成小县城比赛来打，你就可以获得胜利🏆
5️⃣ 注意那个小胖子👀
6️⃣ kop决赛最后一首歌开始前手部不要做任何动作，不然你会被空口鉴leak大神光速出警🚨😱
7️⃣ wonders 🌈✨"""
_2085 = """
啊🤪～啊🤪～啊咦😬啊咦😬啊→啊↑啊↓😨啊😰～嗯💥哎哎🤗哎哦哎嗯😋～哦哎🥳爱爱爱爱爱😍
啊🤪～啊🤪～啊咦😬啊咦😬啊→啊↑啊↓😨啊😰～嗯💥嗯嗯👿滴嘚滴嘚😈唔😱嘟⬅️嘟↖️嘟⬆️嘟↗️嘟➡️嘟↘️嘟⬇️
"""
ABS_TEST_LINES = _kop7 if G_type == "maimai" else _2085

def style_key(name):
    return f"style_{G_type}_{st.session_state.get('style_ui_revision', 0)}_{name}"


def refresh_style_widgets():
    st.session_state.style_ui_revision = st.session_state.get('style_ui_revision', 0) + 1


saved_style = read_style(G_type, video_style_config_path)
if st.session_state.get(f"style_saved_{G_type}") != saved_style:
    st.session_state[f"style_saved_{G_type}"] = deepcopy(saved_style)
    st.session_state[f"style_draft_{G_type}"] = deepcopy(saved_style)
    refresh_style_widgets()
current_style = st.session_state[f"style_draft_{G_type}"]


def save_style_config(style_config, is_custom_style):
    if is_custom_style:
        style_config["style_name"] = "Custom"
    write_style(G_type, style_config, video_style_config_path)
    st.session_state[f"style_saved_{G_type}"] = read_style(G_type, video_style_config_path)
    st.success("样式配置已保存！", icon="✅")



def format_file_path(file_path):
    # if file_path.startswith("./static/"):
    #     return file_path.replace("./static/", "/app/static/")
    return file_path


def save_uploaded_file(uploaded_file, directory):
    if uploaded_file is None:
        return None
    # UploadedFile IDs belong to Streamlit's uploader; no content hashes.
    cache = st.session_state.setdefault("style_uploaded_files", {})
    token = (G_type, directory, uploaded_file.file_id)
    if token not in cache or not Path(cache[token]).is_file():
        Path(directory).mkdir(parents=True, exist_ok=True)
        destination = Path(directory) / f"{uuid4().hex}{Path(uploaded_file.name).suffix.lower()}"
        destination.write_bytes(uploaded_file.getbuffer())
        cache[token] = str(destination)
    return cache[token]


@st.dialog("恢复本游戏默认样式")
def reset_custom_style_dialog():
    st.write("恢复本游戏的默认样式。已上传文件保留，其他游戏的设置不受影响。")
    if st.button("确认重置"):
        style = preset_style(G_type, RESET_STYLES[G_type])
        save_style_config(style, is_custom_style=False)
        st.session_state[f"style_draft_{G_type}"] = style
        refresh_style_widgets()
        st.rerun()

@st.dialog("来点抽象测试文案？")
def show_test_lines_dialog():
    st.text(ABS_TEST_LINES)
    if st.button("好嘞，这就复制"):
        pyperclip.copy(ABS_TEST_LINES)
        st.success("已复制到剪贴板！")


def update_preview_images(style_config, placeholder, test_string):

    record_templates = {
        "maimai":{
                "achievements": "101.0000",
                "ds": 14.4,
                "dxScore": 2889,
                "fc": "app",
                "fs": "fsdp",
                "level": "14",
                "level_index": 3,
                "level_label": "MASTER",
                "ra": 324,
                "rate": "sssp",
                "title": "テストです #狂った民族２ PRAVARGYAZOOQA",
                "type": 1,
            },
        "chunithm":{
                "score": 1010000,
                "ds_cur": 14.5,
                "ds_next": 14.6,
                "ds_cn": 14.4,
                "ds_latest": 14.6,
                "combo_type": "ajc",
                "chain_type": "fcr",
                "level_index": 3,
                "level_label": "MASTER",
                "ra": 16.55,
                "title": "管弦楽組曲 第3番 ニ長調「第2曲（G線上のアリア）」BWV.1068-2",
                "artist": "月鈴 那知（ヴァイオリン） 伴奏：イロドリミドリ",
            },
    }

    intro_template = {
        "clip_title_name": "clip_0",
        "duration": 2,
        "text": test_string
    }

    content_template = {
        "clip_title_name": "Clip_0",
        "main_image": "",
        "bg_image": "",
        "video": os.path.join(default_static_dir, "bg_clips", "black_bg.mp4"),
        "duration": 2,
        "start": 1,
        "end": 3,
        "text": test_string
    }
    
    with placeholder.container(border=True):
        st.info("提示：此效果仅供预览您的自定义样式修改，需要点击下方按钮保存方可生效！")

        # Render Preview 1
        pil_img1 = get_video_preview_frame(
            game_type=G_type,
            clip_config=intro_template,
            style_config=style_config,
            resolution=G_config.get("VIDEO_RES", (1920, 1080)),
            part="intro"
        )
        st.image(pil_img1, caption="预览图1(片头)")
        ending_frame = get_video_preview_frame(
            G_type, intro_template, style_config, G_config.get("VIDEO_RES", (1920, 1080)), part="ending")
        st.image(ending_frame, caption="片尾预览")

        # Render Preview 2
        # generate test image
        test_image_path = os.path.join(temp_static_dir, "test_achievement.png")
        record_template = record_templates.get(G_type)
        content_template['main_image'] = test_image_path
        # BUG: CHECK GENERATE IMAGE
        generate_single_image(
            game_type=G_type,
            style_config=style_config,
            record_detail=record_template,
            output_path=test_image_path,
            title_text="--TEST CLIP --"
        )

        # get preivew video frame
        pil_img2 = get_video_preview_frame(
            game_type=G_type,
            clip_config=content_template,
            style_config=style_config,
            resolution=G_config.get("VIDEO_RES", (1920, 1080)),
            part="content"
        )
        st.image(pil_img2, caption="预览图2(正片)")


def show_current_style_preview(to_preview_style=None):
    with st.container(border=True):
        st.subheader("当前样式预览")

        st.info("如果上传了自定义素材文件，请在保存样式后点击下方按钮刷新预览。")
        if st.button("刷新预览"):
            st.rerun()

        current_asset_config = to_preview_style["asset_paths"]
        
        # 创建两列布局
        preview_col1, preview_col2 = st.columns(2)
        
        with preview_col1:
            st.write("视频素材")

            st.write("- 背景视频预览（片头）")
            intro_video_bg_path = current_asset_config["intro_video_bg"]
            if intro_video_bg_path:
                # 确保使用绝对路径
                if not os.path.isabs(intro_video_bg_path):
                    intro_video_bg_path = os.path.abspath(intro_video_bg_path)
                
                if os.path.exists(intro_video_bg_path):
                    try:
                        # 验证文件可读
                        with open(intro_video_bg_path, 'rb') as f:
                            pass
                        st.video(intro_video_bg_path, format="video/mp4")
                    except (OSError, IOError) as e:
                        st.error(f"无法读取片头视频背景文件: {e}")
                        st.caption(f"文件路径: {intro_video_bg_path}")
                    except Exception as e:
                        error_msg = str(e)
                        if "MediaFileStorageError" in error_msg or "No media file with id" in error_msg:
                            st.warning("⚠️ 视频文件引用已失效，请刷新页面")
                            st.caption(f"文件路径: {intro_video_bg_path}")
                        else:
                            st.error(f"无法加载片头视频背景: {e}")
                            st.caption(f"文件路径: {intro_video_bg_path}")
                else:
                    st.error(f"找不到片头视频背景：{intro_video_bg_path}")
            else:
                st.warning("未配置片头视频背景路径")

            if to_preview_style["options"].get("content_use_video_bg", False) and "content_bg_video" in current_asset_config:
                st.write("- 背景视频预览（正片）")
                content_video_bg_path = current_asset_config["content_bg_video"]
                if content_video_bg_path:
                    # 确保使用绝对路径
                    if not os.path.isabs(content_video_bg_path):
                        content_video_bg_path = os.path.abspath(content_video_bg_path)
                    
                    if os.path.exists(content_video_bg_path):
                        try:
                            # 验证文件可读
                            with open(content_video_bg_path, 'rb') as f:
                                pass
                            st.video(content_video_bg_path, format="video/mp4")
                        except (OSError, IOError) as e:
                            st.error(f"无法读取正片视频背景文件: {e}")
                            st.caption(f"文件路径: {content_video_bg_path}")
                        except Exception as e:
                            error_msg = str(e)
                            if "MediaFileStorageError" in error_msg or "No media file with id" in error_msg:
                                st.warning("⚠️ 视频文件引用已失效，请刷新页面")
                                st.caption(f"文件路径: {content_video_bg_path}")
                            else:
                                st.error(f"无法加载正片视频背景: {e}")
                                st.caption(f"文件路径: {content_video_bg_path}")
                    else:
                        st.error(f"找不到正片视频背景：{content_video_bg_path}")
                else:
                    st.warning("未配置正片视频背景路径")
            else:
                st.markdown("> 正片未启用动态视频背景。")

            st.write("- 背景图片预览（片头）")
            intro_text_bg_path = current_asset_config["intro_text_bg"]
            if os.path.exists(intro_text_bg_path):
                st.image(intro_text_bg_path, caption="片头片尾文字背景图片")
            else:
                st.error(f"找不到片头片尾文字背景图片：{intro_text_bg_path}")

            if to_preview_style["options"].get("override_content_default_bg", False) and "content_bg" in current_asset_config:
                st.write("- 背景图片预览（正片）")
                content_bg_path = current_asset_config["content_bg"]
                if os.path.exists(content_bg_path):
                    st.image(content_bg_path, caption="正片默认背景图片")
                else:
                    st.error(f"找不到正片内容背景图片：{content_bg_path}")
            else:
                st.markdown("> 正片未启用自定义同一背景图片。")

        with preview_col2:
            for section, label in (("intro", "片头"), ("ending", "片尾")):
                st.write(f"{label}背景音乐")
                bgm_path = current_asset_config[f"{section}_bgm"]
                if os.path.isfile(bgm_path):
                    st.audio(bgm_path, format="audio/wav" if Path(bgm_path).suffix.lower() == ".wav" else "audio/mp3")
                else:
                    st.error(f"找不到{label}背景音乐：{bgm_path}")

            st.write("字体文件")
            st.write(f"片头片尾字体: {os.path.basename(current_asset_config['ui_font'])}")
            # TODO: 显示一段该字体的测试文字
            st.write(f"评论文本字体: {os.path.basename(current_asset_config['comment_font'])}")

# =============================================================================
# Page layout starts here
# ==============================================================================

st.header("自定义视频素材和样式")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

st.write("在这里配置视频生成时使用的背景图片、背景音乐、字体等素材。")

tab1, tab2 = st.tabs(["预设样式", "自定义样式"])

with tab1:
    st.subheader("选择预设样式")
    style_options = [item["style_name"] for item in DEFAULT_STYLES[G_type]]
    selected_base = current_style.get("base_style_name")
    selected = st.radio("视频样式预设", options=style_options,
                        index=style_options.index(selected_base) if selected_base in style_options else 0,
                        format_func=lambda name: "MAGiCAL" if name == "Magical" else name,
                        key=style_key("preset"))
    if current_style.get("style_name") == "Custom":
        st.warning("应用预设样式将覆盖已保存的自定义设置。")
    if st.button("应用预设", type="primary"):
        style = preset_style(G_type, selected)
        if G_type == "chunithm":
            style["options"]["chunithm_constant_display"] = constant_mode(current_style)
        save_style_config(style, is_custom_style=False)
        st.session_state[f"style_draft_{G_type}"] = style
        refresh_style_widgets()
        st.rerun()
    show_current_style_preview(current_style)

with tab2:
    custom_setting_area = st.container(border=True)

    # 自定义区域
    with custom_setting_area:
        st.subheader("自定义视频样式")

        # 添加上传文件的版权声明，用户自己对上传的内容负责
        st.markdown("""
        **⚠️注意**：**您上传素材文件即代表您确认所用资源不违反有关法律法规，本工具的开发者不对任何由您自定义内容产生和传播的视频负责。**""")
        
        current_asset_config = current_style["asset_paths"]
        current_options = current_style["options"]
        current_itext = current_style["intro_text_style"]
        current_ctext = current_style["content_text_style"]
        
        # 创建两列布局
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("视频素材设置")
            # 片头背景上传
            uploaded_intro_video_bg = st.file_uploader("片头片尾背景视频",
                                                    help="片头/片尾时位于视频最底层的动态背景，若不指定则使用预设的背景视频",
                                                    type=["mp4", "mov"], key=style_key("intro_video_bg"))
            if uploaded_intro_video_bg:
                file_path = save_uploaded_file(uploaded_intro_video_bg, os.path.join(user_static_dir, "bg_clips"))
                if file_path:
                    current_asset_config["intro_video_bg"] = format_file_path(file_path)
                    st.success(f"已上传：{uploaded_intro_video_bg.name}")

            uploaded_intro_text_bg = st.file_uploader("片头片尾文本框图片",
                                                    help="放置于片头片尾视频的中央作为文本框的背景图片。\
                                                        注意：因为该图片直接叠放在视频上方，所以只有其四周为透明背景的情况下才不会遮挡背景视频，如自定义制作，请使用png格式。\
                                                        若不指定则使用预设的背景图片",
                                                    type=["png"], key=style_key("intro_bg"))
            if uploaded_intro_text_bg:
                file_path = save_uploaded_file(uploaded_intro_text_bg, os.path.join(user_static_dir, "backgrounds"))
                if file_path:
                    current_asset_config["intro_text_bg"] = format_file_path(file_path)
                    st.success(f"已上传：{uploaded_intro_text_bg.name}")
                    

            st.info("注意：上传的素材默认将被拉伸到16:9比例；如果同时上传了片头/片尾的背景图片和视频，图片将被叠放在视频上方。")
            
            st.divider()

            current_options["content_use_video_bg"] = st.checkbox(
                label="正片背景使用动态视频背景",
                help="如果勾选了，将使用 版本预设 / 自定义上传 的背景视频作为正片的动态背景，与自定义背景图片的选项互斥。",
                value=current_options.get("content_use_video_bg", False),
                key=style_key("enable_content_video_bg"))
            
            current_options["override_content_default_bg"] = st.checkbox(
                label="不使用动态视频背景，而使用自定义背景图片",
                help="强制所有正片的背景为图片，如果勾选，请在下方上传默认图片，您也可以在配置视频详情页面为每个片段上传单独的背景图片。",
                value=current_options.get("override_content_default_bg", False),
                key=style_key("enable_custom_content_bg"))

            # 正片背景上传
            uploaded_content_bg = st.file_uploader("自定义正片背景图片（默认）",
                                                help="如果确定所有正片背景都需要使用自定义图片，请在此上传。",
                                                type=["png", "jpg", "jpeg"], key=style_key("video_bg"))
            if uploaded_content_bg:
                file_path = save_uploaded_file(uploaded_content_bg, os.path.join(user_static_dir, "backgrounds"))
                if file_path:
                    current_asset_config["content_bg"] = format_file_path(file_path)
                    st.success(f"已上传：{uploaded_content_bg.name}")
            

            st.divider()
            st.write("背景音乐")
            base_names = [item["style_name"] for item in DEFAULT_STYLES[G_type]]
            if current_style.get("base_style_name") not in base_names:
                current_style["base_style_name"] = st.selectbox(
                    "恢复音乐时使用的基础主题", base_names, key=style_key("base_theme"))
            for section, label in (("intro", "片头"), ("ending", "片尾")):
                uploaded = st.file_uploader(f"{label}背景音乐", type=["mp3", "wav"], key=style_key(f"{section}_bgm"))
                if uploaded is not None:
                    token = (G_type, section, uploaded.file_id)
                    cache = st.session_state.setdefault("bgm_uploaded_files", {})
                    try:
                        if token not in cache or not Path(cache[token]).is_file():
                            with st.spinner("正在检查音频……"):
                                cache[token] = save_bgm_upload(uploaded.name, uploaded.getvalue(),
                                    Path(user_static_dir) / "audios", G_type, section)
                        current_asset_config[f"{section}_bgm"] = cache[token]
                        current_style.setdefault("bgm_display_names", {})[section] = uploaded.name
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
                bgm_path = current_asset_config[f"{section}_bgm"]
                st.caption(current_style.get("bgm_display_names", {}).get(section) or Path(bgm_path).name)
                if os.path.isfile(bgm_path):
                    st.audio(bgm_path, format="audio/wav" if Path(bgm_path).suffix.lower() == ".wav" else "audio/mp3")
                if st.button(f"恢复{label}主题默认音乐", key=style_key(f"reset_{section}_bgm")):
                    base = preset_style(G_type, current_style["base_style_name"])
                    current_asset_config[f"{section}_bgm"] = base["asset_paths"][f"{section}_bgm"]
                    current_style.get("bgm_display_names", {}).pop(section, None)
                    refresh_style_widgets()
                    st.rerun()
            if G_type == "chunithm":
                st.caption("中二默认音乐暂沿用现有音频，可分别上传替换。")
                current_options["chunithm_constant_display"] = st.radio(
                    "定数展示选项", list(CONSTANT_MODES),
                    index=list(CONSTANT_MODES).index(constant_mode(current_style)),
                    format_func=CONSTANT_MODES.get, horizontal=True, key=style_key("constant_mode"))
            st.caption("修改后请保存自定义样式。短音乐会循环至片段结束。")
            st.divider()
            # 预览调整
            test_str = st.text_area("【测试】样式预览",
                                    placeholder="输入任意文本，以预览素材/文本样式调整的效果", 
                                    height=480,
                                    key=style_key("comment_preview_text_area"))
            sub_col1, sub_col2 = st.columns([2, 1])
            with sub_col1:
                preview_btn = st.button("生成预览图", type="primary")
            with sub_col2:
                add_test_lines_btn = st.button("需要文案", icon="❓", type="tertiary")
                if add_test_lines_btn:
                    show_test_lines_dialog()
        
        with col2:
            st.write("字体设置")
            # 成绩图字体上传
            uploaded_text_font = st.file_uploader("成绩图字体", type=["ttf", "otf"], 
                                                help="这个字体将应用于成绩图中的曲名和标题名称",
                                                key=style_key("text_font"))
            if uploaded_text_font:
                file_path = save_uploaded_file(uploaded_text_font, os.path.join(user_static_dir, "fonts"))
                if file_path:
                    current_asset_config["ui_font"] = format_file_path(file_path)
                    st.success(f"已上传：{uploaded_text_font.name}")
            
            # 文本字体上传
            uploaded_comment_font = st.file_uploader("文本字体", type=["ttf", "otf"],
                                                    help="这个字体将应用于片头片尾和心得体会的评论文本", 
                                                    key=style_key("comment_font"))
            if uploaded_comment_font:
                file_path = save_uploaded_file(uploaded_comment_font, os.path.join(user_static_dir, "fonts"))
                if file_path:
                    current_asset_config["comment_font"] = format_file_path(file_path)
                    st.success(f"已上传：{uploaded_comment_font.name}")
                    

            with st.expander("片头片尾文本样式调整"):
                current_itext["font_size"] = st.number_input("片头片尾文本字体大小", min_value=10, max_value=400,
                            value=current_itext.get("font_size", 44), key=style_key("intro_font_size"))
                current_itext["interline"] = st.slider("片头片尾文本字体行距", min_value=1.0, max_value=20.0, step=0.1,
                            value=current_itext.get("interline", 6.5), key=style_key("intro_line_spacing"))
                current_itext["horizontal_align"] = st.selectbox("片头片尾文本对齐方式",
                    options=["left", "center", "right"],
                    index=["left", "center", "right"].index(current_itext.get("horizontal_align", "left")),
                    key=style_key("intro_horizontal_align")
                )
                current_itext["inline_max_chara"] = st.number_input("片头片尾文本每行最大字数", min_value=1, max_value=100,
                                help="每行文本的最大字符数，超过此长度将自动换行。注意：此项设置过大可能导致文本超出画面",
                                value=current_itext.get("inline_max_chara", 26), key=style_key("intro_inline_max_chara"))
                current_itext["font_color"] = st.color_picker("片头片尾文本字体颜色", value=current_itext.get("font_color", "#FFFFFF"), key=style_key("intro_font_color"))
                current_itext["enable_stroke"] = st.checkbox("片头片尾文本字体描边", value=current_itext.get("enable_stroke", True), key=style_key("intro_enable_stroke"))
                if current_itext.get("enable_stroke", False):
                    current_itext["stroke_color"] = st.color_picker("片头片尾文本字体描边颜色", value=current_itext.get("stroke_color", "#000000"), key=style_key("intro_stroke_color"))
                    current_itext["stroke_width"] = st.slider("片头片尾文本字体描边宽度", min_value=1, max_value=10,
                            value=current_itext.get("stroke_width", 2), key=style_key("intro_stroke_width"))
        
            with st.expander("评论文本样式调整"):
                current_ctext["font_size"] = st.number_input("评论字体大小", min_value=10, max_value=360, 
                        value=current_ctext.get("font_size", 28), key=style_key("comment_font_size"))
                current_ctext["interline"] = st.slider("评论字体行距", min_value=1.0, max_value=20.0, step=0.1,
                        value=current_ctext.get("interline", 6.5), key=style_key("comment_line_spacing"))
                current_ctext["horizontal_align"] = st.selectbox("评论文本对齐方式",
                    options=["left", "center", "right"],
                    index=["left", "center", "right"].index(current_ctext.get("horizontal_align", "left")),
                    key=style_key("comment_horizontal_align")
                )
                current_ctext["inline_max_chara"] = st.number_input("评论每行最大字数", min_value=1, max_value=100,
                                help="每行文本的最大字符数，超过此长度将自动换行。注意：此项设置过大可能导致文本超出画面",
                                value=current_ctext.get("inline_max_chara", 24), key=style_key("comment_inline_max_chara"))
                current_ctext["font_color"] = st.color_picker("评论字体颜色", value=current_ctext.get("font_color", "#FFFFFF"), key=style_key("comment_font_color"))
                current_ctext["enable_stroke"] = st.checkbox("字体描边", value=current_ctext.get("enable_stroke", True), key=style_key("comment_enable_stroke"))
                if current_ctext.get("enable_stroke", False):
                    current_ctext["stroke_color"] = st.color_picker("评论字体描边颜色", value=current_ctext.get("stroke_color", "#000000"), key=style_key("comment_stroke_color"))
                    current_ctext["stroke_width"] = st.slider("评论字体描边宽度", min_value=1, max_value=10, 
                            value=current_ctext.get("stroke_width", 2), key=style_key("comment_stroke_width"))

        preview_image_placeholder = st.empty()
        if preview_btn:
            update_preview_images(deepcopy(current_style), preview_image_placeholder, test_str)

        st.divider()
        if st.button("保存自定义样式", type="primary"):
            # 保存当前样式配置
            save_style_config(current_style, is_custom_style=True)

        # 重置自定义样式按钮
        if st.button("恢复本游戏默认样式"):
            reset_custom_style_dialog()


