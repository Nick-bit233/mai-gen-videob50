import streamlit as st
from utils.PageUtils import change_theme, get_game_type_text, update_music_metadata, DEFAULT_STYLE_CONFIG_FILE_PATH, get_db_manager
from db_utils.DataMigration import old_data_migration
from utils.themes import THEME_COLORS, DEFAULT_STYLES
from utils.WebAgentUtils import st_init_cache_pathes
import datetime
import os
import json
from pathlib import Path

def should_update_metadata(threshold_hours=24):
    """
    检查是否需要更新乐曲元数据
    
    Args:
        threshold_hours: 更新的时间阈值（小时）
        
    Returns:
        bool: 是否需要更新
    """
    # 在用户目录下创建配置目录
    config_dir = Path.home() / ".mai-gen-videob50"
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "metadata_update.json"
    
    current_time = datetime.datetime.now()
    
    # 如果配置文件不存在，则创建并立即返回True
    if not config_file.exists():
        with open(config_file, "w") as f:
            json.dump({"last_update": current_time.isoformat()}, f)
        return True
    
    # 读取上次更新时间
    try:
        with open(config_file, "r") as f:
            data = json.load(f)
            last_update = datetime.datetime.fromisoformat(data.get("last_update", "2000-01-01T00:00:00"))
    except (json.JSONDecodeError, ValueError):
        # 文件损坏或格式错误，重新创建
        with open(config_file, "w") as f:
            json.dump({"last_update": current_time.isoformat()}, f)
        return True
    
    # 计算时间差
    time_diff = current_time - last_update
    if time_diff.total_seconds() / 3600 >= threshold_hours:
        # 更新时间戳
        with open(config_file, "w") as f:
            json.dump({"last_update": current_time.isoformat()}, f)
        return True
    
    return False

@st.dialog("刷新主题")
def refresh_theme(theme_name=None):
    st.info("主题已更改，要刷新并应用主题吗？")
    if st.button("刷新并应用", key=f"confirm_refresh_theme"):
        if theme_name:
            st.session_state.theme = theme_name
        st.toast("新主题已应用！")
        st.rerun()

st.image("md_res/icon.png", width=256)

G_type = st.session_state.get('game_type', 'maimai')
cur_version = "v1.0"  # TODO: read from database table

st.title("Mai-gen Videob50 视频生成器")

st.write(f"当前版本: {cur_version} alpha test")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")
st.markdown(
    """
    请按照下列引导步骤操作，以生成您的B50视频。

    详细使用说明请参考：[Github](https://github.com/Nick-bit233/mai-gen-videob50)
    """)

st.info("本工具的缓存数据均保存在本地，如您在编辑过程中意外退出，可在任意步骤加载已有存档继续编辑。")
st.info("在使用过程中，请不要随意刷新页面。如果因为误刷新页面导致索引丢失，建议重新加载存档，并回到第一步检查数据完整性。")
st.success("使用过程中遇到任何问题，可以前往Github页面发起issue，或加入QQ群：994702414 反馈")

st_init_cache_pathes()

# 初始化视频模板样式配置
if not os.path.exists(DEFAULT_STYLE_CONFIG_FILE_PATH):
    default_style_config = DEFAULT_STYLES.get(cur_version, DEFAULT_STYLES['v1.0'])
    with open(DEFAULT_STYLE_CONFIG_FILE_PATH, "w") as f:
        json.dump(default_style_config, f, indent=4)

# 初始化数据库
try:
    db_manager = get_db_manager()
    st.success("🗃️ 数据库已连接并准备就绪。")
except Exception as e:
    st.error(f"初始化数据库时出错: {e}")

if G_type == "maimai":
    switch_btn_text = "切换到中二节奏视频生成器"
else:
    switch_btn_text = "切换到舞萌DX视频生成器"

if st.button(switch_btn_text):
    st.session_state.game_type = "chunithm" if G_type == "maimai" else "maimai"
    # 清空已加载的存档信息
    st.session_state.pop('archive_id', None)
    st.session_state.pop('archive_name', None)
    st.session_state.pop('archive_meta', None)
    st.session_state.pop('records', None)
    st.session_state.data_updated_step1 = False
    # 改变默认主题
    if st.session_state.game_type == "maimai":
        change_theme(THEME_COLORS["maimai"]["Circle"])
        refresh_theme(theme_name="Circle")
    else:
        change_theme(THEME_COLORS["chunithm"]["Verse"])
        refresh_theme(theme_name="Verse")

if G_type == "maimai":
    st.write("从旧版本导入数据")
    with st.container(border=True):
        st.write("如果您有旧版本的存档数据，可以点击下面的按钮，选择旧版本文件夹导入您的历史数据。")
        st.warning("请勿重复导入数据，以免造成冗余损坏。")
        if st.button("导入数据"):
            try:
                old_data_migration() # TODO: 未开发完成
                st.success("数据导入成功！")
            except Exception as e:
                st.error(f"导入数据时出错: {e}")

st.write("单击下面的按钮开始。在开始制作前，您也可以考虑先自定义视频模板的样式。")

col1, col2 = st.columns(2)
with col1:
    if st.button("开始使用", key="start_button"):
        st.switch_page("st_pages/Setup_Achievements.py")
with col2:
    if st.button("视频模板样式设置", key="style_button"):
        st.switch_page("st_pages/Custom_Video_Style_Config.py")

# 检查乐曲元数据
st.write("更新乐曲元数据")
with st.container(border=True):
    try:
        # 检查乐曲元数据更新（设定24小时更新冷却时间）
        metadata_path = "./music_metadata/maimaidx/dxdata.json"
        if should_update_metadata(24) or not os.path.exists(metadata_path):
            update_music_metadata()
            st.success("乐曲元数据已更新")
        else:
            st.info("最近已更新过乐曲元数据，如有需要可以点击下方按钮手动更新")
            if st.button("更新乐曲元数据"):
                update_music_metadata()
                st.success("乐曲元数据已更新")
    except Exception as e:
        st.error(f"更新乐曲元数据时出错: {e}")

st.write("外观选项")
with st.container(border=True):
    if 'theme' not in st.session_state:
        st.session_state.theme = "Default"

    options = ['Default'] + list(THEME_COLORS[G_type].keys())
    theme = st.segmented_control("更改页面主题",
                                 options, 
                                 default=st.session_state.theme,
                                 selection_mode="single")
    if st.button("确定"):
        change_theme(THEME_COLORS[G_type].get(theme, None))
        refresh_theme(theme_name=theme)
