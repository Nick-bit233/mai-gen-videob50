import streamlit as st
import os
import json
import traceback
from utils.PageUtils import *

st.header("Step 4-2: 编辑片头/片尾内容")

G_config = read_global_config()

def edit_context_widget(name, config):
    # 创建一个container来容纳所有组件
    container = st.container(border=True)
    
    # 在session_state中存储当前配置列表
    if f"{name}_items" not in st.session_state:
        st.session_state[f"{name}_items"] = config[name]
    
    items = st.session_state[f"{name}_items"]
    
    with container:
        # 添加新元素的按钮
        if st.button(f"添加一页", key=f"add_{name}"):
            new_item = {
                "id": f"{name}_{len(items) + 1}",
                "duration": 10,
                "text": "【请填写内容】"
            }
            items.append(new_item)
            st.session_state[f"{name}_items"] = items
            st.rerun()
        
        # 为每个元素创建编辑组件
        for idx, item in enumerate(items):
            with st.expander(f"{name} 展示：第 {idx + 1} 页", expanded=True):
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
            if st.button("删除最后一页", key=f"delete_{name}"):
                items.pop()
                st.session_state[f"{name}_items"] = items
                st.rerun()

        
        # 保存按钮
        if st.button("保存更改", key=f"save_{name}"):
            try:
                # 更新配置
                config[name] = items
                ## 保存当前配置
                save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                st.toast("配置已保存！")
            except Exception as e:
                st.error(f"保存失败：{str(e)}")
                st.error(traceback.format_exc())

config = load_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json")
if config:
    st.write("添加想要展示的文字内容，每一页最多可以展示约250字")

    # 分为两栏，左栏读取intro部分的配置，右栏读取outro部分的配置
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("片头配置")
        edit_context_widget("intro", config)
    with col2:
        st.subheader("片尾配置")
        edit_context_widget("ending", config)

    st.write("配置完毕后，请点击下面按钮进入视频生成步骤（请注意两边都要点击保存）")
    if st.button("进行下一步"):
        st.switch_page("st_pages/6_Compostie_Videoes.py")

