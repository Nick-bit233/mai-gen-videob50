import streamlit as st
import traceback
import os

from datetime import datetime
from utils.PageUtils import load_style_config, open_file_explorer, read_global_config, write_global_config, get_game_type_text
from utils.DataUtils import filter_records_by_best_group
from utils.PathUtils import get_user_media_dir
from utils.VideoUtils import render_all_video_clips, combine_full_video_direct, combine_full_video_ffmpeg_concat_gl, render_complete_full_video, combine_from_cached_batches
from utils.Variables import HARD_RENDER_METHOD
from db_utils.DatabaseDataHandler import get_database_handler

# 使用缓存来加速页面加载
@st.cache_data(ttl=300)  # 缓存5分钟
def get_cached_config():
    return read_global_config()

@st.cache_data(ttl=300)
def get_cached_style_config(game_type):
    return load_style_config(game_type=game_type)

@st.cache_data(ttl=60)  # 缓存1分钟
def get_cached_user_save_list(username, game_type):
    db_handler = get_database_handler()
    return db_handler.get_user_save_list(username, game_type=game_type)

@st.cache_data(ttl=60)
def get_cached_full_config(username, archive_name, scope):
    db_handler = get_database_handler()
    main_configs, intro_configs, ending_configs = db_handler.load_full_config_for_composite_video(
        username=username,
        archive_name=archive_name
    )
    include_newbest = scope != 'past'
    include_pastbest = scope != 'new'
    main_configs = filter_records_by_best_group(main_configs, include_newbest, include_pastbest)
    return main_configs, intro_configs, ending_configs

G_config = get_cached_config()
G_type = st.session_state.get('game_type', 'maimai')
style_config = get_cached_style_config(G_type)
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

# 添加清除缓存按钮（仅在需要时显示）
col_user, col_cache = st.columns([3, 1])
with col_user:
    pass  # 用户名显示区域
with col_cache:
    if st.button("🔄 刷新数据", help="清除缓存并重新加载数据", key="refresh_cache"):
        # 清除相关缓存
        get_cached_user_save_list.clear()
        get_cached_full_config.clear()
        st.rerun()

archives = get_cached_user_save_list(username, G_type)

data_name = "B30" if G_type == "chunithm" else "B50"
with st.expander(f"更换{data_name}存档"):
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
_video_bitrate = G_config.get('VIDEO_BITRATE', 5000)
_video_fps = G_config.get('VIDEO_FPS', 60)  # 默认60帧
_trans_enable = G_config['VIDEO_TRANS_ENABLE']
_trans_time = G_config['VIDEO_TRANS_TIME']
_inner_trans_enable = G_config.get('VIDEO_INNER_TRANS_ENABLE', False)

options = ["仅生成每个视频片段", "生成完整视频"]
with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        mode_str = st.radio("选择视频生成模式", 
                options=options, 
                index=_mode_index)
    with col2:
        force_render_clip = st.checkbox("生成视频片段时，强制覆盖已存在的视频文件", value=False)
    with col3:
        use_hardware_acceleration = st.checkbox("使用 GPU 硬件加速", value=False, 
                                                help="一定程度上可提升渲染速度和分担 CPU 负载，但画质可能会降低")
    
    acceleration_method = None
    if use_hardware_acceleration:
        acceleration_method = st.radio("选择您的加速方案", ["NVIDIA", "AMD", "Intel"],
            captions=["CUDA + NVENCoder(NVENC)", "Advanced Media Framework(含集显)", "Quick Sync Video(含集显)"],
            horizontal=True, index=0
        )
        st.info(f"""
        使用 {acceleration_method} 硬件加速：
        - 如您使用 GPU 加速出现如下问题，请考虑使用软件编码：
            - 一使用 GPU 加速就提示失败，随后跳快速生成
            - 调用 GPU 编码和软件编码速度并无巨大差别
        - 若 GPU（或驱动）太旧而不支持当前 FFmpeg 版本将无法使用硬件加速
        """, icon="ℹ️")

trans_config_placeholder = st.empty()
with trans_config_placeholder.container(border=True):
    st.markdown("##### 片段过渡设置")
    st.caption("（仅对生成完整视频模式有效）")
    col_trans1, col_trans2 = st.columns([1, 2])
    with col_trans1:
        trans_enable = st.checkbox("启用片段过渡", value=_trans_enable,
                                  help="在视频片段之间添加淡入淡出过渡效果")
    with col_trans2:
        if trans_enable:
            trans_time = st.number_input(
                "过渡时间（秒）", 
                min_value=0.1, 
                max_value=30.0, 
                value=_trans_time, 
                step=0.1,
                help="设置每个片段之间的过渡时间。建议值：0.5-2.0秒。较长的过渡时间会让视频更平滑，但会增加总时长。"
            )
            st.caption(f"💡 当前设置：每个片段之间会有 {trans_time} 秒的交叉淡入淡出过渡效果")
        else:
            trans_time = _trans_time  # 保持原值，即使禁用
    inner_trans_enable = st.checkbox(
        "批次内片段过渡（分批模式）",
        value=_inner_trans_enable,
        help="仅在启用分批处理时生效：控制同一批次的小片段之间是否添加过渡效果。"
    )
with st.container(border=True):
    st.write("视频分辨率")
    col1, col2 = st.columns(2)
    v_res_width = col1.number_input("视频宽度", min_value=360, max_value=4096, value=_video_res[0])
    v_res_height = col2.number_input("视频高度", min_value=360, max_value=4096, value=_video_res[1])
    if v_res_width % 2 != 0 or v_res_height % 2 != 0:
        adjusted_w = v_res_width - (v_res_width % 2)
        adjusted_h = v_res_height - (v_res_height % 2)
        st.warning(f"分辨率需要为偶数，已自动调整为 {adjusted_w}x{adjusted_h} 以避免编码失败。")
        v_res_width, v_res_height = adjusted_w, adjusted_h

with st.container(border=True):
    st.write("视频比特率(kbps)")  
    v_bitrate = st.number_input("视频比特率", min_value=1000, max_value=10000, value=_video_bitrate)

with st.container(border=True):
    st.write("视频帧率(fps)")
    fps_index = 0 if _video_fps == 30 else 1
    v_fps = st.radio("选择视频帧率", options=[30, 60], index=fps_index, horizontal=True,
                     help="30帧：生成速度更快，文件更小；60帧：画面更流畅，但生成时间更长，文件更大")

v_mode_index = options.index(mode_str)
v_bitrate_kbps = f"{v_bitrate}k"

user_media_paths = get_user_media_dir(username, game_type=G_type)
video_output_path = user_media_paths['output_video_dir']

if not os.path.exists(video_output_path):
    os.makedirs(video_output_path)

# 读取存档的 video_config，只读，用于生成视频
try:
    scope = st.session_state.get('best_group_scope', G_config.get('BEST_GROUP_SCOPE', 'all'))
    main_configs, intro_configs, ending_configs = get_cached_full_config(username, archive_name, scope)
except Exception as e:
    st.error(f"读取存档配置失败: {e}")
    with st.expander("错误详情"):
        st.error(traceback.format_exc())
    st.stop()

# 缓存视频检测（在生成视频之前检测）
temp_batches_dir = os.path.join(video_output_path, "temp_batches")
cached_batch_files = {}
cached_intro_file = None
cached_ending_file = None

if os.path.exists(temp_batches_dir):
    all_files = [f for f in os.listdir(temp_batches_dir) if f.endswith(".mp4")]
    
    for file in sorted(all_files):
        file_path = os.path.join(temp_batches_dir, file)
        if file.startswith("batch_"):
            # 提取批次编号
            try:
                batch_num = int(file.replace("batch_", "").replace(".mp4", ""))
                cached_batch_files[batch_num] = {
                    'filename': file,
                    'path': file_path,
                    'size': os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
                }
            except ValueError:
                pass
        elif file == "intro.mp4":
            cached_intro_file = {
                'filename': file,
                'path': file_path,
                'size': os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
            }
        elif file == "ending.mp4":
            cached_ending_file = {
                'filename': file,
                'path': file_path,
                'size': os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
            }

# 分批处理设置（在 main_configs 加载后显示）
with st.container(border=True):
    st.markdown("##### 内存管理设置（推荐）")
    enable_batch_processing = st.checkbox("启用分批处理", value=True,
                                         help="分批处理可以避免内存不足问题，特别适合处理大量视频（如50+个）")
    batch_size = None
    if enable_batch_processing:
        batch_size = st.number_input("每批处理的视频数量", 
                                     min_value=1, 
                                     max_value=100, 
                                     value=10,
                                     help="建议值：内存充足时10-20个，内存不足时5-10个。如果遇到内存错误，请减小此值。")
        num_batches = (len(main_configs) + batch_size - 1) // batch_size if batch_size else 1
        st.info(f"💡 当前设置：将分 {num_batches} 批处理 {len(main_configs)} 个主要视频片段")
    
    # 显示缓存文件并允许用户选择（在内存管理设置中显示）
    if cached_batch_files or cached_intro_file or cached_ending_file:
        st.divider()
        st.markdown("##### 缓存视频管理")
        st.info(f"💡 检测到 {len(cached_batch_files)} 个批次缓存文件" + 
                (f", 1 个开场文件" if cached_intro_file else "") +
                (f", 1 个结尾文件" if cached_ending_file else "") +
                "。您可以选择哪些文件需要重新生成。")
        
        with st.expander("📋 缓存文件列表和选择", expanded=False):
            # 存储用户选择
            if 'cache_selection' not in st.session_state:
                st.session_state.cache_selection = {}
            
            # 开场文件选择
            if cached_intro_file:
                intro_key = f"cache_intro"
                use_cache_intro = st.checkbox(
                    f"✅ 使用缓存: {cached_intro_file['filename']} ({cached_intro_file['size']:.1f} MB)",
                    value=True,
                    key=intro_key,
                    help="取消勾选将重新生成开场片段"
                )
                st.session_state.cache_selection['intro'] = use_cache_intro
            
            # 批次文件选择
            if cached_batch_files:
                st.write("**批次文件：**")
                # 按批次编号排序
                sorted_batches = sorted(cached_batch_files.items())
                
                # 使用列布局显示
                cols_per_row = 3
                for i in range(0, len(sorted_batches), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for j, (batch_num, file_info) in enumerate(sorted_batches[i:i+cols_per_row]):
                        with cols[j]:
                            batch_key = f"cache_batch_{batch_num}"
                            use_cache = st.checkbox(
                                f"✅ 批次 {batch_num}: {file_info['size']:.1f} MB",
                                value=True,
                                key=batch_key,
                                help=f"取消勾选将重新生成批次 {batch_num}"
                            )
                            st.session_state.cache_selection[f'batch_{batch_num}'] = use_cache
            
            # 结尾文件选择
            if cached_ending_file:
                ending_key = f"cache_ending"
                use_cache_ending = st.checkbox(
                    f"✅ 使用缓存: {cached_ending_file['filename']} ({cached_ending_file['size']:.1f} MB)",
                    value=True,
                    key=ending_key,
                    help="取消勾选将重新生成结尾片段"
                )
                st.session_state.cache_selection['ending'] = use_cache_ending

def save_video_render_config():
    # 保存配置
    G_config['ONLY_GENERATE_CLIPS'] = v_mode_index == 0
    G_config['VIDEO_RES'] = (v_res_width, v_res_height)
    G_config['VIDEO_BITRATE'] = v_bitrate
    G_config['VIDEO_FPS'] = v_fps
    G_config['VIDEO_TRANS_ENABLE'] = trans_enable
    G_config['VIDEO_TRANS_TIME'] = trans_time
    G_config['VIDEO_INNER_TRANS_ENABLE'] = inner_trans_enable
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
                        style_config=style_config,
                        main_configs=main_configs,
                        video_output_path=video_output_path,
                        video_res=video_res,
                        video_bitrate=v_bitrate_kbps,
                        intro_configs=intro_configs,
                        ending_configs=ending_configs,
                        auto_add_transition=trans_enable,
                        trans_time=trans_time,
                        force_render=force_render_clip,
                        use_hardware_acceleration=use_hardware_acceleration if 'use_hardware_acceleration' in locals() else False,
                        acceleration_method=acceleration_method if 'acceleration_method' in locals() else None
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
                
                # 创建进度条和状态显示
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(info):
                    """更新进度条的回调函数"""
                    progress = info.get('progress', 0)
                    stage = info.get('stage', '')
                    
                    progress_bar.progress(progress)
                    
                    # 根据阶段显示不同的状态信息
                    if stage == 'batch_processing':
                        current_batch = info.get('current_batch', 0)
                        total_batches = info.get('total_batches', 0)
                        status_text.info(f"正在处理第 {current_batch}/{total_batches} 批视频片段... ({int(progress * 100)}%)")
                    elif stage == 'clip_processing':
                        current_clip = info.get('current_clip', 0)
                        total_clips = info.get('total_clips', 0)
                        current_batch = info.get('current_batch', 0)
                        total_batches = info.get('total_batches', 0)
                        status_text.info(f"批次 {current_batch}/{total_batches} - 处理片段 {current_clip}/{total_clips}... ({int(progress * 100)}%)")
                    elif stage == 'batch_compositing':
                        current_batch = info.get('current_batch', 0)
                        total_batches = info.get('total_batches', 0)
                        status_text.info(f"正在合成第 {current_batch}/{total_batches} 批视频... ({int(progress * 100)}%)")
                    elif stage == 'loading_temp_files':
                        current_file = info.get('current_file', 0)
                        total_files = info.get('total_files', 0)
                        if current_file:
                            status_text.info(f"正在加载临时文件 {current_file}/{total_files}... ({int(progress * 100)}%)")
                        else:
                            status_text.info(f"正在加载临时文件... ({int(progress * 100)}%)")
                    elif stage == 'merging_videos':
                        status_text.info(f"正在合并视频文件... ({int(progress * 100)}%)")
                    elif stage == 'rendering_final':
                        status_text.info(f"正在渲染最终视频... ({int(progress * 100)}%)")
                    elif stage == 'completed':
                        status_text.success("视频生成完成！")
                
                # 准备缓存选择信息
                cache_selection = st.session_state.get('cache_selection', {})
                skip_cache = {}  # 需要跳过的缓存文件（用户选择使用缓存的）
                
                if cache_selection:
                    # 检查哪些批次应该使用缓存（跳过生成）
                    if cache_selection.get('intro', False) and cached_intro_file:
                        skip_cache['intro'] = cached_intro_file['path']
                    if cache_selection.get('ending', False) and cached_ending_file:
                        skip_cache['ending'] = cached_ending_file['path']
                    for batch_num, file_info in cached_batch_files.items():
                        if cache_selection.get(f'batch_{batch_num}', False):
                            skip_cache[f'batch_{batch_num}'] = file_info['path']
                
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
                        video_trans_enable=trans_enable,
                        video_trans_time=trans_time,
                        full_last_clip=False,
                        use_hardware_acceleration=use_hardware_acceleration if 'use_hardware_acceleration' in locals() else False,
                        acceleration_method=acceleration_method if 'acceleration_method' in locals() else None,
                        batch_size=batch_size if 'batch_size' in locals() and enable_batch_processing else None,
                        progress_callback=update_progress,
                        video_fps=v_fps,
                        skip_cache_files=skip_cache if skip_cache else None,
                        batch_inner_trans_enable=inner_trans_enable if enable_batch_processing else False
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

# 从缓存文件合成最终视频
st.write("### 从缓存文件合成最终视频")
st.info("如果之前生成失败但缓存文件已存在，可以使用此功能直接从缓存文件合成最终视频，无需重新生成。")
with st.container(border=True):
    if os.path.exists(temp_batches_dir):
        cached_files = [f for f in os.listdir(temp_batches_dir) if f.endswith(".mp4")]
        if cached_files:
            st.success(f"找到 {len(cached_files)} 个缓存文件")
            
            if st.button("从缓存文件合成最终视频", key="combine_from_cache"):
                save_video_render_config()
                video_res = (v_res_width, v_res_height)
                
                placeholder_cache = st.empty()
                with placeholder_cache.container(border=True, height=560):
                    st.warning("生成过程中请不要手动跳转到其他页面，或刷新本页面，否则可能导致生成失败！")
                    
                    # 创建进度条和状态显示
                    progress_bar_cache = st.progress(0)
                    status_text_cache = st.empty()
                    
                    def update_progress_cache(info):
                        """更新进度条的回调函数"""
                        progress = info.get('progress', 0)
                        stage = info.get('stage', '')
                        
                        progress_bar_cache.progress(progress)
                        
                        if stage == 'loading_cached_files':
                            current_file = info.get('current_file', 0)
                            total_files = info.get('total_files', 0)
                            if current_file:
                                status_text_cache.info(f"正在加载缓存文件 {current_file}/{total_files}... ({int(progress * 100)}%)")
                            else:
                                status_text_cache.info(f"正在加载缓存文件... ({int(progress * 100)}%)")
                        elif stage == 'merging_videos':
                            status_text_cache.info(f"正在合并视频文件... ({int(progress * 100)}%)")
                        elif stage == 'rendering_final':
                            status_text_cache.info(f"正在渲染最终视频... ({int(progress * 100)}%)")
                        elif stage == 'completed':
                            status_text_cache.success("视频生成完成！")
                    
                    output_file = os.path.join(video_output_path, f"{username}_FULL_VIDEO.mp4")
                    output_info = combine_from_cached_batches(
                        temp_batches_dir=temp_batches_dir,
                        output_file=output_file,
                        use_hardware_acceleration=use_hardware_acceleration if 'use_hardware_acceleration' in locals() else False,
                        acceleration_method=acceleration_method if 'acceleration_method' in locals() else None,
                        video_bitrate=v_bitrate_kbps,
                        progress_callback=update_progress_cache,
                        fps=v_fps,
                        trans_enable=trans_enable,
                        trans_time=trans_time
                    )
                    st.write(f"【{output_info['info']}")
                st.success("从缓存文件合成完成！点击下方按钮打开视频所在文件夹")
        else:
            st.warning("缓存目录存在但没有找到缓存文件")
    else:
        st.info("未找到缓存目录，请先使用正常方式生成视频")

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
                force_render=force_render_clip,
                use_hardware_acceleration=use_hardware_acceleration if 'use_hardware_acceleration' in locals() else False,
                acceleration_method=acceleration_method if 'acceleration_method' in locals() else None
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
                    force_render=force_render_clip,
                    use_hardware_acceleration=use_hardware_acceleration if 'use_hardware_acceleration' in locals() else False,
                    acceleration_method=acceleration_method if 'acceleration_method' in locals() else None
                )
                st.info("已启动批量视频片段生成，请在控制台窗口查看进度……")
            with st.spinner("正在拼接视频……"):
                combine_full_video_ffmpeg_concat_gl(video_output_path, trans_name, trans_time)
                st.info("已启动视频拼接任务，请在控制台窗口查看进度……")
            st.success("所有任务已退出，请从上方按钮打开文件夹查看视频生成结果")
