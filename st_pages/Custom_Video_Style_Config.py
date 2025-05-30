import streamlit as st
import os
import json
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from utils.PageUtils import read_global_config, write_global_config, DEFAULT_STYLES, DEFAULT_STYLE_CONFIG_FILE_PATH
from utils.PathUtils import get_data_paths, get_user_versions

st.header("视频样式配置")

DEFAULT_STYLE_KEY = "Prism"
video_style_config_path = DEFAULT_STYLE_CONFIG_FILE_PATH

# 配置素材文件夹
default_static_dir = "./static/assets"
user_static_dir = "./static/user"
os.makedirs(user_static_dir, exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "backgrounds"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "audios"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "fonts"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "bg_clips"), exist_ok=True)

# 读取全局配置
G_config = read_global_config()

# 从配置中读取当前样式设定，若没有则使用默认样式
has_custom_style = G_config.get("USE_CUSTOM_VIDEO_STYLE", False)

if os.path.exists(video_style_config_path):
    with open(video_style_config_path, "r") as f:
        custom_styles = json.load(f)
    current_style = custom_styles
else:
    current_style = deepcopy(DEFAULT_STYLES[DEFAULT_STYLE_KEY])

def save_style_config(style_config, is_custom_style):
    """保存样式配置到文件"""
    with open(video_style_config_path, "w") as f:
        json.dump(style_config, f, indent=4)
    
    # 更新全局配置
    G_config["USE_CUSTOM_VIDEO_STYLE"] = is_custom_style
    write_global_config(G_config)
    st.rerun()

def format_file_path(file_path):
    # if file_path.startswith("./static/"):
    #     return file_path.replace("./static/", "/app/static/")
    return file_path

def save_uploaded_file(uploaded_file, directory):
    """保存上传的文件并返回保存路径"""
    if uploaded_file is None:
        return None
    
    # 确保目录存在
    os.makedirs(directory, exist_ok=True)
    
    # 生成文件名（使用原始文件名）
    file_path = os.path.join(directory, uploaded_file.name)
    
    # 保存文件
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path

@st.dialog("确认重置自定义样式")
def reset_custom_style_dialog():
    st.warning("确定要重置所有自定义样式设置吗？此操作将删除已上传的自定义文件，且不可撤销！")
    if st.button("确认重置"):
        # 删除所有自定义文件
        user_bg_dir = os.path.join(user_static_dir, "backgrounds")
        user_music_dir = os.path.join(user_static_dir, "audios")
        user_fonts_dir = os.path.join(user_static_dir, "fonts")
        user_video_dir = os.path.join(user_static_dir, "bg_clips")
        
        for dir_path in [user_bg_dir, user_music_dir, user_fonts_dir, user_video_dir]:
            for file_name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        
        # 恢复默认样式
        current_style = deepcopy(DEFAULT_STYLES[DEFAULT_STYLE_KEY])
        save_style_config(current_style, is_custom_style=False)

        st.success("已重置所有自定义样式！")
        st.rerun()

# UI部分
st.write("在这里配置视频生成时使用的背景图片、背景音乐、字体等素材。")
st.info("请注意：更改样式设置后，需要点击底部的【保存设置】按钮才能生效。")

# 样式选择区域
with st.container(border=True):
    st.subheader("选择预设样式")
    
    # 样式选择菜单
    style_options = list(DEFAULT_STYLES.keys())

    selected_style_name = st.radio(
        "视频样式预设",
        options=style_options,
        index=0
    )
    if st.button("应用"):
        # 切换样式时加载对应配置
        if selected_style_name in DEFAULT_STYLES:
            current_style = deepcopy(DEFAULT_STYLES[selected_style_name])
            current_options = selected_style_name
            # 保存配置
            save_style_config(current_style, is_custom_style=False)
            st.success(f"已切换到{selected_style_name}！")
        else:
            st.error(f"未找到预设样式资源：{selected_style_name}")

# 如果选择自定义样式，显示上传文件区域
with st.container(border=True):
    st.subheader("自定义视频样式")

    current_asset_config = current_style["asset_paths"]
    current_options = current_style["options"]
    
    # 创建两列布局
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("视频素材设置")
        # 片头背景上传
        uploaded_intro_text_bg = st.file_uploader("片头片尾文字背景图片", type=["png", "jpg", "jpeg"], key="intro_bg")
        if uploaded_intro_text_bg:
            file_path = save_uploaded_file(uploaded_intro_text_bg, os.path.join(user_static_dir, "backgrounds"))
            if file_path:
                current_asset_config["intro_text_bg"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_intro_text_bg.name}")

        uploaded_intro_video_bg = st.file_uploader("片头片尾背景视频", type=["mp4", "mov"], key="intro_video_bg")
        if uploaded_intro_video_bg:
            file_path = save_uploaded_file(uploaded_intro_video_bg, os.path.join(user_static_dir, "bg_clips"))
            if file_path:
                current_asset_config["intro_video_bg"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_intro_video_bg.name}")

        st.info("注意：上传的素材默认将被拉伸到16:9比例；如果同时上传了片头/片尾的背景图片和视频，图片将被叠放在视频上方。")
        
        # 正片视频背景上传
        uploaded_content_bg = st.file_uploader("正片内容背景图片", type=["png", "jpg", "jpeg"], key="video_bg")
        if uploaded_content_bg:
            file_path = save_uploaded_file(uploaded_content_bg, os.path.join(user_static_dir, "backgrounds"))
            if file_path:
                current_asset_config["content_bg"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_content_bg.name}")
        
        st.checkbox(
            label="使用正片内容背景图片替换默认曲绘背景",
            value=current_options.get("enable_custom_content_bg", True),
            key="enable_custom_content_bg")

        # 背景音乐上传
        uploaded_intro_bgm = st.file_uploader("片头片尾背景音乐", type=["mp3", "wav"], key="intro_bgm")
        if uploaded_intro_bgm:
            file_path = save_uploaded_file(uploaded_intro_bgm, os.path.join(user_static_dir, "audios"))
            if file_path:
                current_asset_config["intro_bgm"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_intro_bgm.name}")
    
    with col2:
        st.write("字体设置")
        # 文本字体上传
        uploaded_text_font = st.file_uploader("主要文本字体（曲名和UI）", type=["ttf", "otf"], key="text_font")
        if uploaded_text_font:
            file_path = save_uploaded_file(uploaded_text_font, os.path.join(user_static_dir, "fonts"))
            if file_path:
                current_asset_config["ui_font"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_text_font.name}")
        
        # 评论字体上传
        uploaded_comment_font = st.file_uploader("评论文本字体", type=["ttf", "otf"], key="comment_font")
        if uploaded_comment_font:
            file_path = save_uploaded_file(uploaded_comment_font, os.path.join(user_static_dir, "fonts"))
            if file_path:
                current_asset_config["comment_font"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_comment_font.name}")
    
        # TODO:详细字体设置
        with st.expander("评论字体参数调整"):
            st.slider("评论字体大小", min_value=10, max_value=50, value=current_options.get("comment_font_size", 24), key="comment_font_size")
            st.slider("评论字体行距", min_value=1.0, max_value=3.0, value=current_options.get("comment_line_spacing", 1.0), key="comment_line_spacing")
            st.number_input("评论每行最大字体数", min_value=1, max_value=100, value=current_options.get("comment_inline_max_chara", 48), key="comment_inline_max_chara")

            # 预览调整
            st.text_area("评论文本预览", placeholder="输入任意文本，以预览字体调整效果", key="comment_preview_text")
            if st.button("生成预览图片"):
                pass


    if st.button("保存自定义样式"):
        # 保存当前样式配置
        save_style_config(current_style, is_custom_style=True)
        st.success("自定义样式已保存！")

    # 重置自定义样式按钮
    if st.button("重置所有自定义样式"):
        reset_custom_style_dialog()

# 显示当前样式预览
# TODO: 区域手动刷新
with st.container(border=True):
    st.subheader("当前样式预览")

    current_asset_config = current_style["asset_paths"]
    
    # 创建两列布局
    preview_col1, preview_col2 = st.columns(2)
    
    with preview_col1:
        st.write("视频素材")

        st.write("- 背景视频预览")
        intro_video_bg_path = current_asset_config["intro_video_bg"]
        if os.path.exists(intro_video_bg_path):
            st.video(intro_video_bg_path, format="video/mp4")
        else:
            st.error(f"找不到片头视频背景：{intro_video_bg_path}")

        st.write("- 背景图片预览")
        intro_text_bg_path = current_asset_config["intro_text_bg"]
        if os.path.exists(intro_text_bg_path):
            st.image(intro_text_bg_path, caption="片头片尾文字背景图片")
        else:
            st.error(f"找不到片头片尾文字背景图片：{intro_text_bg_path}")

        content_bg_path = current_asset_config["content_bg"]
        if os.path.exists(content_bg_path):
            st.image(content_bg_path, caption="正片内容背景图片")
        else:
            st.error(f"找不到正片内容背景图片：{content_bg_path}")

    with preview_col2:
        st.write("片头片尾背景音乐")

        intro_bgm_path = current_asset_config["intro_bgm"]
        if os.path.exists(intro_bgm_path):
            st.audio(intro_bgm_path, format="audio/mp3")
        else:
            st.error(f"找不到背景音乐：{intro_bgm_path}")
        
        st.write("字体文件")
        st.write(f"主要文本字体: {os.path.basename(current_asset_config['ui_font'])}")
        st.write(f"评论文本字体: {os.path.basename(current_asset_config['comment_font'])}")

st.markdown("---")
st.info("提示：修改的样式将应用于下一次视频生成。如果您已经生成过视频片段，可能需要重新生成才能看到效果。")
