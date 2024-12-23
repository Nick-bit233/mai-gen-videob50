import streamlit as st
import subprocess
import traceback
from main_gen import generate_complete_video, generate_one_video_clip
from utils.PageUtils import *

st.header("Step 5: 视频生成")

st.info("在执行视频生成前，请确保已经完成了4-1和4-2步骤，并且检查所有填写的配置无误。")

G_config = read_global_config()

st.write("视频生成相关设置")

_mode_index = 0 if G_config['ONLY_GENERATE_CLIPS'] else 1
_video_res = G_config['VIDEO_RES']
_video_bitrate = 5000 # TODO：存储到配置文件中
_trans_enable = G_config['VIDEO_TRANS_ENABLE']
_trans_time = G_config['VIDEO_TRANS_TIME']

options = ["仅生成每个视频片段（不包含片头片尾）", "生成完整视频"]
with st.container(border=True):
    mode_str = st.radio("选择视频生成模式", 
            options=options, 
            index=_mode_index)

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

if st.button("开始生成视频"):
    # 保存配置
    G_config['ONLY_GENERATE_CLIPS'] = v_mode_index == 0
    G_config['VIDEO_RES'] = (v_res_width, v_res_height)
    G_config['VIDEO_BITRATE'] = v_bitrate
    G_config['VIDEO_TRANS_ENABLE'] = trans_enable
    G_config['VIDEO_TRANS_TIME'] = trans_time
    write_global_config(G_config)
    st.toast("配置已保存！")

    video_output_path = f"./videos/{G_config['USER_ID']}"
    if not os.path.exists(video_output_path):
        os.makedirs(video_output_path)
    video_configs = load_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json")
    video_res = (v_res_width, v_res_height)

    placeholder = st.empty()
    if v_mode_index == 0:
        try:
            with placeholder.container(border=True, height=560):
                st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                with st.spinner("正在生成所有视频片段……"):
                    progress_bar = st.progress(0)
                    write_container = st.container(border=True, height=400)
                    i = 0
                    config_clip_list = video_configs['main']
                    for config in config_clip_list:
                        i += 1
                        progress_bar.progress(i / len(config_clip_list), text=f"正在生成视频片段({i}/{len(config_clip_list)})")
                        output_info = generate_one_video_clip(config=config, 
                                                    video_output_path=video_output_path, 
                                                    video_res=video_res, 
                                                    video_bitrate=v_bitrate_kbps)
                        write_container.write(f"【{i}/{len(config_clip_list)}】{output_info['info']}")
            st.success("视频片段生成结束！请在弹出的文件夹窗口中查看")
            abs_path = os.path.abspath(video_output_path)
            st.info(f"如果未能打开文件夹，可在此路径中查看生成视频：{abs_path}")
            open_file_explorer(abs_path)
        except Exception as e:
            st.error(f"视频片段生成失败，错误详情: {traceback.print_exc()}")

    else:
        try:
            with placeholder.container(border=True, height=560):
                st.info("请注意，生成完整视频通常需要一定时间，您可以在控制台窗口中查看进度")
                st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                with st.spinner("正在生成完整视频……"):
                    output_info = generate_complete_video(configs=video_configs, 
                                                    username=G_config['USER_ID'],
                                                    video_output_path=video_output_path, 
                                                    video_res=video_res, 
                                                    video_bitrate=v_bitrate_kbps,
                                                    video_trans_enable=trans_enable, 
                                                    video_trans_time=trans_time, 
                                                    full_last_clip=False)
                    st.write(f"【{output_info['info']}")
            st.success("完整视频生成结束！请在弹出的文件夹窗口中查看")
            abs_path = os.path.abspath(video_output_path)
            st.info(f"如果未能打开文件夹，可在此路径中查看生成视频：{abs_path}")
            open_file_explorer(abs_path)
        except Exception as e:
            st.error(f"完整视频生成失败，错误详情: {traceback.print_exc()}")
