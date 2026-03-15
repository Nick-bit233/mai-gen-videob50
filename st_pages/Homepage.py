import streamlit as st
from utils.PageUtils import change_theme, get_game_type_text, update_music_metadata, DEFAULT_STYLE_CONFIG_FILE_PATH, get_db_manager, clear_all_user_data
from db_utils.DataMigration import old_data_migration
from utils.themes import THEME_COLORS, DEFAULT_STYLES
from utils.WebAgentUtils import st_init_cache_pathes
import datetime
import os
import json
from pathlib import Path

def get_user_config_dir():
    """获取用户配置目录"""
    config_dir = Path.home() / ".mai-gen-videob50"
    config_dir.mkdir(exist_ok=True)
    return config_dir

def save_last_game_type(game_type: str):
    """
    保存用户上次使用的游戏类型
    
    Args:
        game_type: 游戏类型 ('maimai' 或 'chunithm')
    """
    config_dir = get_user_config_dir()
    config_file = config_dir / "user_preferences.json"
    
    try:
        # 读取现有配置
        if config_file.exists():
            with open(config_file, "r", encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {}
        
        # 更新游戏类型
        data["last_game_type"] = game_type
        
        # 保存配置
        with open(config_file, "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass  # 静默处理保存失败

def load_last_game_type() -> str:
    """
    加载用户上次使用的游戏类型
    
    Returns:
        str: 游戏类型，默认为 'maimai'
    """
    config_dir = get_user_config_dir()
    config_file = config_dir / "user_preferences.json"
    
    try:
        if config_file.exists():
            with open(config_file, "r", encoding='utf-8') as f:
                data = json.load(f)
                return data.get("last_game_type", "maimai")
    except (json.JSONDecodeError, Exception):
        pass
    
    return "maimai"

def should_update_metadata(threshold_hours=24):
    """
    检查是否需要更新乐曲元数据
    
    Args:
        threshold_hours: 更新的时间阈值（小时）
        
    Returns:
        bool: 是否需要更新
    """
    # 在用户目录下创建配置目录
    config_dir = get_user_config_dir()
    
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

# 页面头部
col_header1, col_header2 = st.columns([1, 3])
with col_header1:
    st.image("md_res/icon.png", width=200)
with col_header2:
    st.title("mai-gen-videob50 视频生成器")
    # 首次加载时，从配置文件恢复上次的游戏类型
    if 'game_type' not in st.session_state:
        last_game_type = load_last_game_type()
        st.session_state.game_type = last_game_type
        # 根据恢复的游戏类型设置对应主题
        if last_game_type == "maimai":
            if 'theme' not in st.session_state:
                st.session_state.theme = "Circle"
                change_theme(THEME_COLORS["maimai"]["Circle"])
        else:
            if 'theme' not in st.session_state:
                st.session_state.theme = "Verse"
                change_theme(THEME_COLORS["chunithm"]["Verse"])
    G_type = st.session_state.get('game_type', 'maimai')
    st.caption(f"当前版本 v1.1 |\
               Created by: [Nickbit](https://github.com/Nick-bit233), \
               Thanks to: [caiccu](https://github.com/CAICCU), \
               [MetallicAllex](https://github.com/MetallicAllex), \
               [YelonNotXTD](https://github.com/YelonNotXTD) ")
    st.info(f"您正在使用 **{get_game_type_text(G_type)}** 视频生成模式")

# 游戏类型切换
with st.container(border=True):
    if G_type == "maimai":
        switch_btn_text = "🔄 切换到中二节奏视频生成器"
    else:
        switch_btn_text = "🔄 切换到舞萌DX视频生成器"
    
    if st.button(switch_btn_text, use_container_width=True, type="secondary"):
        new_game_type = "chunithm" if G_type == "maimai" else "maimai"
        st.session_state.game_type = new_game_type
        # 保存用户的游戏类型选择
        save_last_game_type(new_game_type)
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

# 欢迎信息和使用指南
st.markdown("### 📖 使用指南")
with st.container(border=True):
    st.markdown(f"""
    👋 欢迎使用 mai-gen-videob50！本工具旨在帮助您轻松生成{get_game_type_text(G_type)}的分表展示视频，请按照以下步骤操作：
    
    1. **获取数据** | 在左侧的**数据管理**页面分组中注册用户名和存档，您可以选择从第三方查分器获取分表，或手动创建自定义分表
    2. **生成和抓取资源** | 在左侧的**资源生成**页面分组中完成： 1）生成成绩图片，2)搜索视频，3)确认正确的视频并下载（需要联网并建议登录相关平台）
    3. **编辑评论** | 在左侧的**评论编辑**页面分组中编辑您需要剪辑的内容，也就是每个视频的展示片段和评论文字
    4. **合成视频** | 全部完成后，前往**合成视频**页面中启动最终的视频渲染过程
    
    详细使用说明请参考：[GitHub](https://github.com/Nick-bit233/mai-gen-videob50)
    """)

# 重要提示
with st.container(border=True):
    st.markdown("### ⚠️ 重要提示（第一次使用请仔细阅读）")
    st.info("**数据缓存**: 本工具的缓存数据均保存在本地，若您中途退出或意外刷新页面，可在任意步骤加载已有存档继续编辑。", icon="💾")
    st.warning(""" **生成时间**: 本工具旨在节省搜集素材与编辑视频步骤中的工作量，而未专门对视频渲染速度进行优化
   
    - 从零开始到获取完整视频的时间受到多种因素影响（如网络速度、视频长度与分辨率、硬件CPU性能等）
    - 我们无法估算准确时间，但**渲染步骤至少需要60分钟，缓慢情况下可能需要 >3小时** (渲染期间，可以正常使用您的设备)
    - 如果您正在使用一台公共或计时设备，请务必注意预留足够的使用时间
  
    """, icon="🕐")
    st.success("**问题反馈**: 使用过程中遇到任何问题，可以前往Github页面发起issue，或加入QQ群：[994702414](https://qm.qq.com/q/ogt02jHEjK) 反馈", icon="💬")

st_init_cache_pathes()

# 初始化视频模板样式配置
if not os.path.exists(DEFAULT_STYLE_CONFIG_FILE_PATH):
    # 根据游戏类型初始化默认样式配置
    default_style_config = {}
    for game_type in ['maimai', 'chunithm']:
        # 获取对应游戏类型的第一个默认样式
        game_styles = DEFAULT_STYLES.get(game_type, [])
        if game_styles:
            default_style_config[game_type] = game_styles[0]
    with open(DEFAULT_STYLE_CONFIG_FILE_PATH, "w", encoding='utf-8') as f:
        json.dump(default_style_config, f, ensure_ascii=False, indent=4)

# 系统状态检查
st.markdown("### 🔧 系统状态")

# 元数据状态 - 根据当前游戏类型检查对应的元数据文件
metadata_ready = False
if G_type == "maimai":
    metadata_path = "./music_metadata/mai_fusion_data.json"
elif G_type == "chunithm":
    metadata_path = "music_metadata/chuni_fusion_data.json"
metadata_ready = os.path.exists(metadata_path)

col_status1, col_status2 = st.columns(2)
with col_status1:
    # 数据库状态
    try:
        db_manager = get_db_manager()
        st.success("🗃️ 数据库已连接并准备就绪")
    except Exception as e:
        st.error(f"❌ 数据库初始化失败: {e}")

with col_status2:
    if metadata_ready:
        st.success("📚 乐曲元数据已就绪")
    else:
        st.warning("⚠️ 乐曲元数据未初始化")

# 主要操作区域
st.markdown("### 🚀 开始使用")
col_start1, col_start2 = st.columns(2)
with col_start1:
    if st.button("🎬 开始制作视频", key="start_button", use_container_width=True, type="primary"):
        st.switch_page("st_pages/Setup_Achievements.py")
with col_start2:
    if st.button("🎨 自定义视频样式", key="style_button", use_container_width=True):
        st.switch_page("st_pages/Custom_Video_Style_Config.py")

# 旧版数据导入 # TODO: 未开发完成
# with st.expander("📥 从旧版本导入数据", expanded=False):
#     st.info("💡 正在施工中，敬请期待")
#     st.write("如果您有旧版本的存档数据，可以点击下面的按钮，选择旧版本文件夹导入您的历史数据。")
#     st.warning("⚠️ 请勿重复导入数据，以免造成冗余损坏。")
#     if st.button("导入数据", key="import_data_btn"):
#         try:
#             old_data_migration()
#             st.success("✅ 数据导入成功！")
#         except Exception as e:
#             st.error(f"❌ 导入数据时出错: {e}")

# 外观设置
st.markdown("### 🎨 外观设置")
with st.container(border=True):
    if 'theme' not in st.session_state:
        st.session_state.theme = "Default"

    options = ['Default'] + list(THEME_COLORS[G_type].keys())
    theme = st.selectbox(
        "选择页面主题",
        options=options,
        index=options.index(st.session_state.theme) if st.session_state.theme in options else 0,
        help="选择您喜欢的主题配色方案"
    )
    
    col_theme1, col_theme2 = st.columns([3, 1])
    with col_theme1:
        st.caption("更改主题配色以匹配您的喜好")
    with col_theme2:
        if st.button("应用主题", key="apply_theme_btn", use_container_width=True):
            change_theme(THEME_COLORS[G_type].get(theme, None))
            refresh_theme(theme_name=theme)

# 乐曲元数据更新
st.divider()
st.markdown("#### 📚 更新乐曲元数据")
with st.container(border=True):
    try:
        # 根据当前游戏类型检查对应的元数据文件
        needs_update = should_update_metadata(24) or not metadata_ready
        if needs_update:
            with st.spinner("正在更新乐曲元数据..."):
                update_music_metadata()
            st.success("✅ 乐曲元数据已更新")
        else:
            st.info("ℹ️ 最近已更新过乐曲元数据（24小时内），如有需要可以手动更新")
            col_meta1, col_meta2 = st.columns([3, 1])
            with col_meta1:
                st.caption("乐曲元数据用于识别和匹配歌曲信息，建议定期更新以获取最新曲目")
            with col_meta2:
                if st.button("🔄 手动更新", key="manual_update_metadata", use_container_width=True):
                    with st.spinner("正在更新..."):
                        update_music_metadata()
                    st.success("✅ 乐曲元数据已更新")
                    st.rerun()
    except Exception as e:
        st.error(f"❌ 更新乐曲元数据时出错: {e}")
        with st.expander("错误详情"):
            import traceback
            st.code(traceback.format_exc())            

# 数据管理（危险区域）
st.markdown("#### ⚠️ 本地数据管理")
with st.container(border=True):
    st.warning("⚠️ **危险操作区域**：以下操作将永久删除数据，请谨慎操作！")
    
    # 获取当前用户名（如果有）
    current_username = st.session_state.get('username', '')
    
    if current_username:
        st.info(f"当前用户: **{current_username}**")
        
        # 清空个人数据按钮
        if 'show_clear_confirm' not in st.session_state:
            st.session_state.show_clear_confirm = False
        
        if not st.session_state.show_clear_confirm:
            if st.button("🗑️ 清空所有个人数据", key="clear_data_btn", type="primary", use_container_width=True):
                st.session_state.show_clear_confirm = True
                st.rerun()
        else:
            st.error("⚠️ **确认清空数据**")
            st.markdown("""
            此操作将永久删除以下内容：
            - 数据库中的所有存档、记录、配置和资源
            - 本地存档文件夹（`b50_datas` 和 `chunithm_datas`）
            - 配置文件中的 API Key 和 Token 等敏感信息
            - 用户配置目录中的相关文件
            
            **此操作不可撤销！**
            """)
            
            col_confirm1, col_confirm2 = st.columns(2)
            with col_confirm1:
                if st.button("✅ 确认清空", key="confirm_clear_btn", type="primary", use_container_width=True):
                    with st.spinner("正在清空数据..."):
                        result = clear_all_user_data(current_username)
                        
                        if result['success']:
                            st.success("✅ 数据清空完成！")
                            
                            # 显示清空详情
                            with st.expander("查看清空详情", expanded=True):
                                st.write(f"**删除的数据库记录：**")
                                st.write(f"- 存档数: {result['deleted_db_records']['archives']}")
                                st.write(f"- 记录数: {result['deleted_db_records']['records']}")
                                st.write(f"- 配置数: {result['deleted_db_records']['configurations']}")
                                st.write(f"- 资源数: {result['deleted_db_records']['assets']}")
                                
                                if result['deleted_files']:
                                    st.write(f"**删除的文件/文件夹：**")
                                    for file in result['deleted_files']:
                                        st.write(f"- {file}")
                                
                                if result['errors']:
                                    st.write(f"**错误信息：**")
                                    for error in result['errors']:
                                        st.error(error)
                            
                            # 清空 session state
                            st.session_state.pop('username', None)
                            st.session_state.pop('archive_id', None)
                            st.session_state.pop('archive_name', None)
                            st.session_state.pop('archive_meta', None)
                            st.session_state.pop('records', None)
                            st.session_state.show_clear_confirm = False
                            
                            st.info("💡 提示：页面将在3秒后自动刷新...")
                            import time
                            time.sleep(3)
                            st.rerun()
                        else:
                            st.error("❌ 清空数据时出现错误")
                            with st.expander("查看错误详情"):
                                for error in result['errors']:
                                    st.error(error)
                            
                            st.session_state.show_clear_confirm = False
                            st.rerun()
            
            with col_confirm2:
                if st.button("❌ 取消", key="cancel_clear_btn", use_container_width=True):
                    st.session_state.show_clear_confirm = False
                    st.rerun()
    else:
        st.info("💡 提示：请先在「获取/管理查分器数据」页面输入用户名后，才能使用此功能。")
