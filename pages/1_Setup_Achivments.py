import streamlit as st
import os
import json
import subprocess
from pre_gen import st_update_b50_data
from utils.PageUtils import *

def show_b50_dataframe(info_placeholder, user_id, data):
    with info_placeholder.container(border=True):
        st.write(f"{user_id}的B50数据预览: ")
        st.dataframe(data, column_order=["clip_id", "title", "level_label", "level",  "ds", "achievements", "fc", "fs", "ra", "dxScore"])

G_config = read_global_config()
username = G_config.get('USER_ID', '')
downloader = G_config.get('DOWNLOADER', 'bilibili')
use_proxy = G_config.get('USE_PROXY', False)
proxy_address = G_config.get('PROXY_ADDRESS', '127.0.0.1:7890')

st.header("Step 1: 配置生成器参数和B50成绩数据")

# 配置输入
username = st.text_input("输入水鱼查分器用户名", value=username)
# 选择下载器
default_index = ["bilibili", "youtube"].index(downloader)
downloader = st.selectbox("选择下载器", ["bilibili", "youtube"], index=default_index)
# 选择是否启用代理
use_proxy = st.checkbox("启用代理", value=use_proxy)
# 输入代理地址，默认值为127.0.0.1:7890
proxy_address = st.text_input("输入代理地址", value=proxy_address, disabled=not use_proxy)

if st.button("保存配置"):
    # 更新配置字典
    G_config['USER_ID'] = username
    G_config['DOWNLOADER'] = downloader
    G_config['USE_PROXY'] = use_proxy
    G_config['PROXY_ADDRESS'] = proxy_address
    # 写入配置文件
    write_global_config(G_config)
    st.success("配置已保存！")
    st.session_state.config_saved = True  # 添加状态标记

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved', False):
    if st.button("获取B50数据"):
        with st.spinner("正在获取B50数据更新..."):
            info_placeholder = st.empty()
            
            # 执使用你现有的pre_gen.py代码）
            res = st_update_b50_data()
            info = res.get("info", "unknown")
            data = res.get("data", None)
            if info == "updated":
                st.success(f"B50数据更新完成，共更新了{len(data)}条数据")
            elif info == "keep":
                st.success(f"B50数据已存在，共更新了{len(data)}条数据")
            else:
                st.error("B50数据更新失败！")
                info_placeholder.write(f"错误信息: {data}")
            if info == "updated" or info == "keep":
                show_b50_dataframe(info_placeholder, username, data)

else:
    st.warning("请先保存配置！")  # 如果未保存配置，给出提示