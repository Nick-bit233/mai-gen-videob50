import streamlit as st
import traceback
import os

from datetime import datetime
from utils.PageUtils import load_style_config, open_file_explorer, read_global_config, write_global_config, get_game_type_text
from utils.PathUtils import get_user_base_dir, get_user_media_dir
from utils.VideoUtils import render_all_video_clips, combine_full_video_direct, combine_full_video_ffmpeg_concat_gl, render_complete_full_video
from db_utils.DatabaseDataHandler import get_database_handler

G_config = read_global_config()
G_type = st.session_state.get('game_type', 'maimai')
style_config = load_style_config()
db_handler = get_database_handler()

# =============================================================================
# Page layout starts here
# ==============================================================================
st.header("Step 5: 视频生成")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

st.info("在执行视频生成前，请确保已经完成了4-1和4-2步骤，并且检查所有填写的配置无误。")

### Savefile Management - Start ###
username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)

if not username:
    st.warning("请先在存档管理页面指定用户名。")
    st.stop()
st.write(f"当前用户名: **{username}**")
archives = db_handler.get_user_save_list(username, game_type=G_type)

with st.expander("更换B50存档"):
    if not archives:
        st.warning("未找到任何存档。请先新建或加载存档。")
        st.stop()
    else:
        archive_names = [a['archive_name'] for a in archives]
        try:
            current_archive_index = archive_names.index(st.session_state.get('archive_name'))
        except (ValueError, TypeError):
            current_archive_index = 0
        
        st.markdown("##### 加载本地存档")
        selected_archive_name = st.selectbox(
            "选择存档进行加载",
            archive_names,
            index=current_archive_index
        )
        if st.button("加载此存档（只需要点击一次！）"):

            archive_id = db_handler.load_save_archive(username, selected_archive_name)
            st.session_state.archive_id = archive_id
        
            archive_data = db_handler.load_archive_metadata(username, selected_archive_name)
            if archive_data:
                st.session_state.archive_name = selected_archive_name
                st.success(f"已加载存档 **{selected_archive_name}**")
                st.rerun()
            else:
                st.error("加载存档数据失败。")
if not archive_id:
    st.warning("未找到有效的存档！")
    st.stop()
### Savefile Management - End ###

st.write("视频生成相关设置")

_mode_index = 0 if G_config['ONLY_GENERATE_CLIPS'] else 1
_video_res = G_config['VIDEO_RES']
_video_bitrate = 5000 # TODO：存储到配置文件中
_trans_enable = G_config['VIDEO_TRANS_ENABLE']
_trans_time = G_config['VIDEO_TRANS_TIME']

options = ["仅生成每个视频片段", "生成完整视频"]
with st.container(border=True):
    mode_str = st.radio("选择视频生成模式", 
            options=options, 
            index=_mode_index)
    
    force_render_clip = st.checkbox("生成视频片段时，强制覆盖已存在的视频文件", value=False)

trans_config_placeholder = st.empty()
with trans_config_placeholder.container(border=True):
    st.write("片段过渡设置（仅对生成完整视频模式有效）")
    trans_enable = st.checkbox("启用片段过渡", value=_trans_enable)
    trans_time = st.number_input("过渡时间", min_value=0.5, max_value=10.0, value=_trans_time, step=0.5,
                                 disabled=not trans_enable)
with st.container(border=True):
    st.write("视频分辨率")
    col1, col2 = st.columns(2)
    v_res_width = col1.number_input("视频宽度", min_value=360, max_value=4096, value=_video_res[0])
    v_res_height = col2.number_input("视频高度", min_value=360, max_value=4096, value=_video_res[1])

with st.container(border=True):
    st.write("视频比特率(kbps)")  
    v_bitrate = st.number_input("视频比特率", min_value=1000, max_value=10000, value=_video_bitrate)

v_mode_index = options.index(mode_str)
v_bitrate_kbps = f"{v_bitrate}k"

user_media_paths = get_user_media_dir(username)
video_output_path = user_media_paths['output_video_dir']

if not os.path.exists(video_output_path):
    os.makedirs(video_output_path)

# 读取存档的 video_config，只读，用于生成视频
try:
    main_configs, intro_configs, ending_configs = db_handler.load_full_config_for_composite_video(username, archive_name)
except Exception as e:
    st.error(f"读取存档配置失败: {e}")
    with st.expander("错误详情"):
        st.error(traceback.format_exc())
    st.stop()

def save_video_render_config():
    # 保存配置
    G_config['ONLY_GENERATE_CLIPS'] = v_mode_index == 0
    G_config['VIDEO_RES'] = (v_res_width, v_res_height)
    G_config['VIDEO_BITRATE'] = v_bitrate
    G_config['VIDEO_TRANS_ENABLE'] = trans_enable
    G_config['VIDEO_TRANS_TIME'] = trans_time
    write_global_config(G_config)
    st.toast("配置已保存！")

if st.button("开始生成视频"):
    save_video_render_config()
    video_res = (v_res_width, v_res_height)

    placeholder = st.empty()
    if v_mode_index == 0:
        try:
            with placeholder.container(border=True, height=560):
                st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                with st.spinner("正在生成所有视频片段……"):
                    render_all_video_clips(
                        game_type=G_type,
                        
                    )
                    st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
            st.success("视频片段生成结束！点击下方按钮打开视频所在文件夹")
        except Exception as e:
            st.error(f"视频片段生成失败，错误详情: {traceback.print_exc()}")

    else:
        try:
            with placeholder.container(border=True, height=560):
                st.info("请注意，生成完整视频通常需要一定时间，您可以在控制台窗口中查看进度")
                st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                with st.spinner("正在生成完整视频……"):
                    output_info = render_complete_full_video(
                        username=username,
                        game_type=G_type,
                        main_configs=main_configs,
                        intro_configs=intro_configs,
                        ending_configs=ending_configs,
                        style_config=style_config,
                        video_output_path=video_output_path,
                        video_res=video_res,
                        video_bitrate=v_bitrate_kbps,
                        auto_add_transition=trans_enable,
                        video_trans_time=trans_time,
                        full_last_clip=False
                    )
                    st.write(f"【{output_info['info']}")
            st.success("完整视频生成结束！点击下方按钮打开视频所在文件夹")
        except Exception as e:
            st.error(f"完整视频生成失败，错误详情: {traceback.print_exc()}")

abs_path = os.path.abspath(video_output_path)
if st.button("打开视频输出文件夹"):
    open_file_explorer(abs_path)
st.write(f"如果打开文件夹失败，请在此路径中寻找生成的视频：{abs_path}")

# 添加分割线
st.divider()

st.write("其他视频生成方案")
st.warning("请注意，此区域的功能未经充分测试，不保证生成视频的效果或稳定性，请谨慎使用。")
with st.container(border=True):
    st.write("【快速模式】先生成所有视频片段，再直接拼接为完整视频")
    st.info("本方案会降低视频生成过程中的内存占用，并减少生成时间，但视频片段之间将只有黑屏过渡。")
    if st.button("直接拼接方式生成完整视频"):
        save_video_render_config()
        video_res = (v_res_width, v_res_height)
        with st.spinner("正在生成所有视频片段……"):
            render_all_video_clips(
                game_type=G_type,
                style_config=style_config,
                main_configs=main_configs,
                video_output_path=video_output_path, 
                video_res=video_res, 
                video_bitrate=v_bitrate_kbps,
                intro_configs=intro_configs,
                ending_configs=ending_configs,
                auto_add_transition=trans_enable, 
                trans_time=trans_time,
                force_render=force_render_clip
            )
            st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
        with st.spinner("正在拼接视频……"):
            combine_full_video_direct(video_output_path)
        st.success("所有任务已退出，请从上方按钮打开文件夹查看视频生成结果")

with st.container(border=True):
    st.write("【更多过渡效果】使用ffmpeg concat生成视频，允许自定义片段过渡效果")
    st.warning("本功能要求先在本地环境中安装ffmpeg concat插件，请务必查看使用说明后进行！")
    @st.dialog("ffmpeg-concat使用说明")
    def delete_video_config_dialog(file):
        ### 展示markdown文本
        # read markdown file
        with open(file, "r", encoding="utf-8") as f:
            doc = f.read()
        st.markdown(doc)

    if st.button("查看ffmpeg concat使用说明", key=f"open_ffmpeg_concat_doc"):
        delete_video_config_dialog("./docs/ffmpeg_concat_Guide.md")

    with st.container(border=True):
        st.write("片段过渡效果")
        trans_name = st.selectbox("选择过渡效果", options=["fade", "circleOpen", "crossWarp", "directionalWarp", "directionalWipe", "crossZoom", "dreamy", "squaresWire"], index=0)
        if st.button("使用ffmpeg concat生成视频"):
            save_video_render_config()
            video_res = (v_res_width, v_res_height)
            with st.spinner("正在生成所有视频片段……"):
                render_all_video_clips(
                    game_type=G_type,
                    style_config=style_config,
                    main_configs=main_configs,
                    video_output_path=video_output_path, 
                    video_res=video_res, 
                    video_bitrate=v_bitrate_kbps,
                    intro_configs=intro_configs,
                    ending_configs=ending_configs,
                    auto_add_transition=trans_enable,
                    trans_time=trans_time,
                    force_render=force_render_clip
                )
                st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
            with st.spinner("正在拼接视频……"):
                combine_full_video_ffmpeg_concat_gl(video_output_path, trans_name, trans_time)
                st.info("已启动视频拼接任务，请在控制台窗口查看进度……")
            st.success("所有任务已退出，请从上方按钮打开文件夹查看视频生成结果")
