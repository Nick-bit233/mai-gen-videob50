import streamlit as st
from utils.PageUtils import change_theme, update_music_metadata
from utils.themes import THEME_COLORS
from pre_gen import st_init_cache_pathes
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

st.image("md_res/icon.png", width=256)

st.title("Mai-gen Videob50 视频生成器")

st.write("当前版本: v0.5.0")

st.markdown(
    """
    请按照下列引导步骤操作，以生成您的B50视频。

    详细使用说明请参考：[Github](https://github.com/Nick-bit233/mai-gen-videob50)
    """)

st.info("本工具的缓存数据均保存在本地，如您在编辑过程中意外退出，可在任意步骤加载已有存档继续编辑。")
st.info("在使用过程中，请不要随意刷新页面。如果因为误刷新页面导致索引丢失，建议重新加载存档，并回到第一步检查数据完整性。")
st.success("使用过程中遇到任何问题，可以前往Github页面发起issue，或加入QQ群：994702414 反馈")

st_init_cache_pathes()

st.write("单击下面的按钮开始")

if st.button("开始使用"):
    st.switch_page("st_pages/1_Setup_Achivments.py")

st.write("更新乐曲数据库")
with st.container(border=True):
    try:
        # 检查乐曲元数据更新（设定24小时更新冷却时间）
        metadata_path = "./music_metadata/maimaidx/songs.json"
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
    @st.dialog("刷新主题")
    def refresh_theme():
        st.info("主题已更改，要刷新并应用主题吗？")
        if st.button("刷新并应用", key=f"confirm_refresh_theme"):
            st.toast("新主题已应用！")
            st.rerun()
        
    options = ["Default", "Festival", "Buddies", "Prism"]
    theme = st.segmented_control("更改页面主题",
                                 options, 
                                 default=st.session_state.theme,
                                 selection_mode="single")
    if st.button("确定"):
        st.session_state.theme = theme
        change_theme(THEME_COLORS.get(theme, None))
        refresh_theme()
