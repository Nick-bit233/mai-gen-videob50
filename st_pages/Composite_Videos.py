import streamlit as st
import traceback
import os
from datetime import datetime

from database.VideoContents import VideoContents
from utils.PageUtils import open_file_explorer, load_full_config_safe, read_global_config, write_global_config
from utils.PathUtils import get_data_paths, get_user_versions, get_main_image_path
from utils.VideoUtils import render_all_video_clips, combine_full_video_direct, combine_full_video_ffmpeg_concat_gl, render_complete_full_video

st.header("Step 5: 视频生成")

st.info("在执行视频生成前，请确保已经完成了4-1和4-2步骤，并且检查所有填写的配置无误。")

G_config = read_global_config()
FONT_PATH = "./font/SOURCEHANSANSSC-BOLD.OTF"

### Savefile Management - Start ###
if "username" in st.session_state:
    st.session_state.username = st.session_state.username

if "save_id" in st.session_state:
    st.session_state.save_id = st.session_state.save_id

username = st.session_state.get("username", None)
save_id = st.session_state.get("save_id", None)
current_paths = None
data_loaded = False

if not username:
    st.error("请先获取指定用户名的B50存档！")
    st.stop()

if save_id:
    # load save data
    current_paths = get_data_paths(username, save_id)
    data_loaded = True
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write("当前存档")
        with col2:
            st.write(f"用户名：{username}，存档时间：{save_id} ")
else:
    st.warning("未索引到存档，请先加载存档数据！")

with st.expander("更换B50存档"):
    st.info("如果要更换用户，请回到存档管理页面指定其他用户名。")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            selected_save_id = st.selectbox(
                "选择存档",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            if st.button("使用此存档（只需要点击一次！）"):
                if selected_save_id:
                    st.session_state.save_id = selected_save_id
                    st.rerun()
                else:
                    st.error("无效的存档路径！")
    else:
        st.warning("未找到任何存档，请先在存档管理页面获取存档！")
        st.stop()
if not save_id:
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

video_output_path = current_paths['output_video_dir']
if not os.path.exists(video_output_path):
    os.makedirs(video_output_path)

# 读取存档的b50 config文件
b50_config_file = current_paths['data_file']
if not os.path.exists(b50_config_file):
    st.error(f"未找到存档配置文件{b50_config_file}，请检查B50存档的数据完整性！")
    st.stop()

try:
    b50_config = load_full_config_safe(b50_config_file, username)
    config_subtype = b50_config.get('sub_type', 'best')
    records = b50_config.get('records', [])
    if config_subtype == "best":
        records.reverse()
except Exception as e:
    st.error(f"读取存档配置文件失败: {e}")
    st.stop()


# 读取存档的video config文件
video_config_file = current_paths['video_config']
if not os.path.exists(video_config_file):
    st.error(f"未找到视频内容配置文件{video_config_file}，请检查前置步骤是否完成，以及B50存档的数据完整性！")
    st.stop()
video_configs = VideoContents(video_config_file)

main_part = []
for record in records:
    clip_info = video_configs.get_item(record)
    clip_info['id'] = record['clip_id']
    clip_info['main_image'] = get_main_image_path(current_paths['image_dir'], record['clip_id'])
    main_part.append(clip_info)
video_configs.main = main_part

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
                    render_all_video_clips(video_configs, video_output_path, video_res, v_bitrate_kbps, 
                                        font_path=FONT_PATH, auto_add_transition=False, trans_time=trans_time,
                                        force_render=force_render_clip)
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
                    output_info = render_complete_full_video(configs=video_configs, 
                                                    username=username,
                                                    video_output_path=video_output_path, 
                                                    video_res=video_res, 
                                                    video_bitrate=v_bitrate_kbps,
                                                    video_trans_enable=trans_enable, 
                                                    video_trans_time=trans_time, 
                                                    full_last_clip=False,
                                                    font_path=FONT_PATH)
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
            render_all_video_clips(video_configs, video_output_path, video_res, v_bitrate_kbps, 
                                   font_path=FONT_PATH, auto_add_transition=trans_enable, trans_time=trans_time,
                                   force_render=force_render_clip)
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
                render_all_video_clips(video_configs, video_output_path, video_res, v_bitrate_kbps, 
                                       font_path=FONT_PATH, auto_add_transition=False, trans_time=trans_time,
                                       force_render=force_render_clip)
                st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
            with st.spinner("正在拼接视频……"):
                combine_full_video_ffmpeg_concat_gl(video_output_path, video_res, trans_name, trans_time)
                st.info("已启动视频拼接任务，请在控制台窗口查看进度……")
            st.success("所有任务已退出，请从上方按钮打开文件夹查看视频生成结果")
