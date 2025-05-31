import streamlit as st
import os
import json
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from utils.themes import DEFAULT_STYLES
from utils.PageUtils import read_global_config, write_global_config, DEFAULT_STYLE_CONFIG_FILE_PATH
from utils.ImageUtils import generate_single_image
from utils.VideoUtils import get_video_preview_frame

st.header("视频样式配置")

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

# 读取全局配置
G_config = read_global_config()

# 从配置中读取当前样式设定，若没有则使用默认样式
has_custom_style = G_config.get("USE_CUSTOM_VIDEO_STYLE", False)

solips = """现在的孩子冲到机厅就是把其他人从机子上赶下来 
然后投币扫码 上机 选择模式 选区域 
旅行伙伴 跳过功能票 然后选中solips开始游戏
然后一个带绝赞的双押划星星 一个双押划星星 再一个双押划星星 
再一个双押划星星 然后一个双押 接下来一堆8分单点 两个16分扫键 
几根管子 两个8分接俩12分三角绝赞拍划
然后划一堆跟空集一样的星星 1181(18)(18) 
又划一堆跟空集一样的星星 8818 五组双押
然后16分交互往下打 一颗绝赞
 一堆8分错位 x x xxxx 5号键拍三下往上滑五条星星
再回来把两条黄星星蹭掉"""

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

def update_preview_images(style_config, placeholder, test_string):

    record_template ={
        "achievements": 101.0,
        "ds": 14.4,
        "dxScore": 2889,
        "fc": "app",
        "fs": "fsdp",
        "level": "14",
        "level_index": 3,
        "level_label": "MASTER",
        "ra": 324,
        "rate": "sssp",
        "song_id": 11461,
        "title": "テストです #狂った民族２ PRAVARGYAZOOQA",
        "type": "DX",
        "clip_name": "Clip_0",
        "clip_id": "clip_0",
    }

    intro_template = {
        "id": "clip_0",
        "duration": 2,
        "text": test_string
    }

    content_template = {
        "id": "clip_0",
        "clip_name": "Clip_0",
        "achievement_title": "テストです #狂った民族２ PRAVARGYAZOOQA",
        "song_id": 11461,
        "level_index": 3,
        "type": "DX",
        "main_image": "",
        "video": os.path.join(default_static_dir, "bg_clips", "black_bg.mp4"),
        "duration": 2,
        "start": 1,
        "end": 3,
        "text": test_string
    }
    
    with placeholder.container(border=True):
        # Render Preview 1
        pil_img1 = get_video_preview_frame(
            clip_config=intro_template,
            style_config=style_config,
            resolution=G_config.get("VIDEO_RES", (1920, 1080)),
            type="maimai",
            part="intro"
        )
        st.image(pil_img1, caption="预览图1(片头)")

        # Render Preview 2
        # generate test image
        test_image_path = os.path.join(temp_static_dir, "test_achievement.png")
        record_template['achievements'] = f"{record_template['achievements']:.4f}"
        content_template['main_image'] = test_image_path
        generate_single_image(
            style_config=style_config,
            record_detail=record_template,
            output_path=test_image_path,
            title_text="--TEST CLIP --"
        )

        # get preivew video frame
        pil_img2 = get_video_preview_frame(
            clip_config=content_template,
            style_config=style_config,
            resolution=G_config.get("VIDEO_RES", (1920, 1080)),
            type="maimai",
            part="content"
        )
        st.image(pil_img2, caption="预览图2(正片)")


# UI部分
st.write("在这里配置视频生成时使用的背景图片、背景音乐、字体等素材。")

# 样式选择区域
with st.container(border=True):
    st.subheader("选择预设样式")
    
    # 样式选择菜单
    style_options = list(DEFAULT_STYLES.keys())

    selected_style_name = st.radio(
        "视频样式预设",
        options=style_options,
        index=1
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

    # 添加上传文件的版权声明，用户自己对上传的内容负责
    st.markdown("""
    **注意**：**您上传素材文件即代表您确认所用资源不违反有关法律法规，本工具的开发者不对任何由您自定义内容产生和传播的视频负责。**""")
    
    current_asset_config = current_style["asset_paths"]
    current_options = current_style["options"]
    current_itext = current_style["intro_text_style"]
    current_ctext = current_style["content_text_style"]
    
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
        
        st.divider()
        # 正片背景上传
        uploaded_content_bg = st.file_uploader("正片默认背景图片", type=["png", "jpg", "jpeg"], key="video_bg")
        if uploaded_content_bg:
            file_path = save_uploaded_file(uploaded_content_bg, os.path.join(user_static_dir, "backgrounds"))
            if file_path:
                current_asset_config["content_bg"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_content_bg.name}")
        
        current_options["override_content_default_bg"] = st.checkbox(
            label="使用此背景图片替换正片中所有默认曲绘背景",
            value=current_options.get("override_content_default_bg", False),
            key="enable_custom_content_bg")

        st.divider()
        # 背景音乐上传
        uploaded_intro_bgm = st.file_uploader("片头片尾背景音乐", type=["mp3", "wav"], key="intro_bgm")
        if uploaded_intro_bgm:
            file_path = save_uploaded_file(uploaded_intro_bgm, os.path.join(user_static_dir, "audios"))
            if file_path:
                current_asset_config["intro_bgm"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_intro_bgm.name}")

        st.divider()
        # 预览调整
        test_str = st.text_area("【测试】样式预览", 
                                placeholder="输入任意文本，以预览素材/文本样式调整效果", 
                                height=480,
                                help=f"需要文案？{solips}",
                                key="comment_preview_text")
        preview_btn = st.button("生成预览图")
    
    with col2:
        st.write("字体设置")
        # 成绩图字体上传
        uploaded_text_font = st.file_uploader("成绩图字体", type=["ttf", "otf"], 
                                              help="这个字体将应用于成绩图中的曲名和标题名称",
                                              key="text_font")
        if uploaded_text_font:
            file_path = save_uploaded_file(uploaded_text_font, os.path.join(user_static_dir, "fonts"))
            if file_path:
                current_asset_config["ui_font"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_text_font.name}")
        
        # 文本字体上传
        uploaded_comment_font = st.file_uploader("文本字体", type=["ttf", "otf"],
                                                help="这个字体将应用于片头片尾和心得体会的评论文本", 
                                                key="comment_font")
        if uploaded_comment_font:
            file_path = save_uploaded_file(uploaded_comment_font, os.path.join(user_static_dir, "fonts"))
            if file_path:
                current_asset_config["comment_font"] = format_file_path(file_path)
                st.success(f"已上传：{uploaded_comment_font.name}")
                

        with st.expander("片头片尾文本样式调整"):
            current_itext["font_size"] = st.slider("片头片尾文本字体大小", min_value=10, max_value=80,
                        value=current_itext.get("font_size", 44), key="intro_font_size")
            current_itext["interline"] = st.slider("片头片尾文本字体行距", min_value=1.0, max_value=20.0, step=0.1,
                        value=current_itext.get("interline", 6.5), key="intro_line_spacing")
            current_itext["horizontal_align"] = st.selectbox("片头片尾文本对齐方式",
                options=["left", "center", "right"],
                index=["left", "center", "right"].index(current_itext.get("horizontal_align", "left")),
                key="intro_horizontal_align"
            )
            current_itext["inline_max_chara"] = st.number_input("片头片尾文本每行最大字数", min_value=1, max_value=100,
                            help="每行文本的最大字符数，超过此长度将自动换行。注意：此项设置过大可能导致文本超出画面",
                            value=current_itext.get("inline_max_chara", 52), key="intro_inline_max_chara")
            current_itext["font_color"] = st.color_picker("片头片尾文本字体颜色", value=current_itext.get("font_color", "#FFFFFF"), key="intro_font_color")
            current_itext["enable_stroke"] = st.checkbox("片头片尾文本字体描边", value=current_itext.get("enable_stroke", True), key="intro_enable_stroke")
            if current_itext.get("enable_stroke", False):
                current_itext["stroke_color"] = st.color_picker("片头片尾文本字体描边颜色", value=current_itext.get("stroke_color", "#000000"), key="intro_stroke_color")
                current_itext["stroke_width"] = st.slider("片头片尾文本字体描边宽度", min_value=1, max_value=10,
                          value=current_itext.get("stroke_width", 2), key="intro_stroke_width")
    
        with st.expander("评论文本样式调整"):
            current_ctext["font_size"] = st.slider("评论字体大小", min_value=10, max_value=80, 
                      value=current_ctext.get("font_size", 28), key="comment_font_size")
            current_ctext["interline"] = st.slider("评论字体行距", min_value=1.0, max_value=20.0, step=0.1,
                      value=current_ctext.get("interline", 6.5), key="comment_line_spacing")
            current_ctext["horizontal_align"] = st.selectbox("评论文本对齐方式",
                options=["left", "center", "right"],
                index=["left", "center", "right"].index(current_ctext.get("horizontal_align", "left")),
                key="comment_horizontal_align"
            )
            current_ctext["inline_max_chara"] = st.number_input("评论每行最大字数", min_value=1, max_value=100,
                            help="每行文本的最大字符数，超过此长度将自动换行。注意：此项设置过大可能导致文本超出画面",
                            value=current_ctext.get("inline_max_chara", 48), key="comment_inline_max_chara")
            current_ctext["font_color"] = st.color_picker("评论字体颜色", value=current_ctext.get("font_color", "#FFFFFF"), key="comment_font_color")
            current_ctext["enable_stroke"] = st.checkbox("字体描边", value=current_ctext.get("enable_stroke", True), key="comment_enable_stroke")
            if current_ctext.get("enable_stroke", False):
                current_ctext["stroke_color"] = st.color_picker("评论字体描边颜色", value=current_ctext.get("stroke_color", "#000000"), key="comment_stroke_color")
                current_ctext["stroke_width"] = st.slider("评论字体描边宽度", min_value=1, max_value=10, 
                          value=current_ctext.get("stroke_width", 2), key="comment_stroke_width")

    preview_image_placeholder = st.empty()
    if preview_btn:
        update_preview_images(deepcopy(current_style), preview_image_placeholder, test_str)

    st.divider()
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
        st.write(f"片头片尾字体: {os.path.basename(current_asset_config['ui_font'])}")
        st.write(f"评论文本字体: {os.path.basename(current_asset_config['comment_font'])}")

st.markdown("---")
st.info("提示：修改的样式将应用于下一次视频生成。如果您已经生成过视频片段，可能需要重新生成才能看到效果。")
