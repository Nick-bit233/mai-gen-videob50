import streamlit as st
import os
import traceback
from utils.PageUtils import read_global_config, get_game_type_text
from db_utils.DatabaseDataHandler import get_database_handler

G_config = read_global_config()
G_type = st.session_state.get('game_type', 'maimai')
db_handler = get_database_handler()

# Streamlit Fragment Function
@st.fragment
def edit_context_widget(ex_config_type, username, archive_name):
    # 创建一个container来容纳所有组件
    container = st.container(border=True)

    ex_key = f"{ex_config_type}_items"
    
    # 在session_state中存储当前配置列表
    if ex_key not in st.session_state:
        # 尝试从数据库读取extra_video_config
        try:
            ex_configs = db_handler.load_extra_video_config(
                    username=username,
                    config_type=ex_config_type,
                    archive_name=archive_name
                )
        except Exception as e:
            st.error(f"读取存档配置失败: {e}")
            with st.expander("错误详情"):
                st.error(traceback.format_exc())
        if not ex_configs or len(ex_configs) == 0:
            # 数据库中没有数据，初始化默认配置
            st.session_state[ex_key] = [
                {
                    "id": f"{ex_config_type}_1",
                    "duration": 10,
                    "text": "【请填写内容】"
                }
            ]
        else:
            # 加载已有配置字典
            st.session_state[ex_key] = [e.get('config_data') for e in ex_configs]

    items = st.session_state[ex_key]
    
    with container:
        # 添加新元素的按钮
        if st.button(f"添加一页", key=f"add_{ex_config_type}"):
            new_item = {
                "id": f"{ex_config_type}_{len(items) + 1}",
                "duration": 10,
                "text": "【请填写内容】"
            }
            items.append(new_item)
            st.session_state[ex_key] = items
            st.rerun(scope="fragment")
        
        # 为每个元素创建编辑组件
        for idx, item in enumerate(items):
            with st.expander(f"{ex_config_type} 展示：第 {idx + 1} 页", expanded=True):
                # 文本编辑框
                new_text = st.text_area(
                    "文本内容",
                    value=item["text"],
                    key=f"{item['id']}_text"
                )
                items[idx]["text"] = new_text
                
                # 持续时间滑动条
                new_duration = st.slider(
                    "持续时间（秒）",
                    min_value=5,
                    max_value=30,
                    value=item["duration"],
                    key=f"{item['id']}_duration"
                )
                items[idx]["duration"] = new_duration
                
        # 删除按钮（只有当列表长度大于1时才显示）
        if len(items) > 1:
            if st.button("删除最后一页", key=f"delete_{ex_config_type}"):
                items.pop()
                st.session_state[ex_key] = items
                st.rerun(scope="fragment")
        
        # 保存按钮
        if st.button("保存更改", key=f"save_{ex_config_type}"):
            try:
                # 更新配置
                st.session_state[ex_key] = items
                ## 保存当前配置
                db_handler.save_extra_video_config(
                    username=username,
                    config_type=ex_config_type,
                    config_data_list=items,
                    archive_name=archive_name
                )
                st.success("配置已保存！")
            except Exception as e:
                st.error(f"保存失败：{str(e)}")
                st.error(traceback.format_exc())

# =============================================================================
# Page layout starts here
# ==============================================================================

st.header("🎬 片头/片尾内容编辑")

st.markdown(f"> 您正在使用 **{get_game_type_text(G_type)}** 视频生成模式。")

### Savefile Management - Start ###
username = st.session_state.get("username", None)
archive_name = st.session_state.get("archive_name", None)
archive_id = st.session_state.get("archive_id", None)

if not username:
    st.warning("请先在存档管理页面指定用户名。")
    st.stop()
st.write(f"当前用户名: **{username}**")
archives = db_handler.get_user_save_list(username, game_type=G_type)

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

st.write("添加想要展示的文字内容，每一页最多可以展示约250字")
st.info("请注意：左右两侧填写完毕后，需要分别点击保存按钮方可生效！")

# 分为两栏，左栏读取intro部分的配置，右栏读取ending部分的配置
col1, col2 = st.columns(2)
with col1:
    st.subheader("片头配置")
    edit_context_widget(ex_config_type="intro", username=username, archive_name=archive_name)
with col2:
    st.subheader("片尾配置")
    edit_context_widget(ex_config_type="ending", username=username, archive_name=archive_name)

st.write("配置完毕后，请点击下面按钮进入视频生成步骤")
if st.button("进行下一步"):
    st.switch_page("st_pages/Composite_Videos.py")


