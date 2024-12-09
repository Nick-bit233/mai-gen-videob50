import streamlit as st
import os
import json
import subprocess
from PIL import Image
import time
import yaml

def load_config(config_file):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_config(config_file, config_data):
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

def read_global_config():
    """读取global_config.yaml文件，返回配置字典"""
    if os.path.exists("global_config.yaml"):
        with open("global_config.yaml", "r", encoding='utf-8') as f:
            return yaml.load(f, Loader=yaml.FullLoader)
    return {}

def write_global_config(config):
    """将配置字典写入global_config.yaml文件"""
    with open("global_config.yaml", "w", encoding='utf-8') as f:
        yaml.dump(config, f)

def main():
    st.set_page_config(page_title="Mai-gen Videob50", layout="wide")
    
    st.title("Mai-gen Videob50 视频生成器")
    
    # 侧边栏：步骤导航
    with st.sidebar:
        st.header("处理步骤")
        step = st.radio(
            "选择当前步骤",
            ["1. 配置参数和素材预生成", "2. 视频内容编辑", "3. 视频生成"]
        )

    # 读取全局配置文件
    G_config = read_global_config()
    username = G_config.get('USER_ID', '')
    downloader = G_config.get('DOWNLOADER', 'bilibili')
    use_proxy = G_config.get('USE_PROXY', False)
    proxy_address = G_config.get('PROXY_ADDRESS', '127.0.0.1:7890')
    
    if step == "1. 配置参数和素材预生成":
        st.header("Step 1: 配置参数和素材预生成")

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
            if st.button("开始预生成"):
                with st.spinner("正在获取数据和下载视频..."):
                    # 创建进度条
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 执行下载过程（使用你现有的pre_gen.py代码）
                    try:
                        # 这里调用你的下载函数，并通过回调更新进度
                        # TODO: 修改pre_gen.py，使其返回回调
                        subprocess.run(["python", "pre_gen.py", username])
                        st.success("下载完成！")
                    except Exception as e:
                        st.error(f"下载失败: {str(e)}")
        else:
            st.warning("请先保存配置！")  # 如果未保存配置，给出提示

    elif step == "2. 视频内容编辑":
        st.header("Step 2: 视频内容编辑")
        
        # 加载配置文件
        config = load_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json")
        if config:
            # 获取所有视频片段的ID
            video_ids = [item['id'] for item in config['main']]
            # 使用session_state来存储当前选择的视频片段索引
            if 'current_index' not in st.session_state:
                st.session_state.current_index = 0

            # 定义回调函数
            def on_video_select():
                # 保存当前配置
                save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                st.success("配置已保存！")
                st.session_state.dummy = str(time.time())  # 更新 session_state 以触发刷新

            # 显示当前视频片段的选择框
            current_id = st.selectbox(
                "选择视频片段", 
                video_ids, 
                index=st.session_state.current_index,
                on_change=on_video_select,
                key="video_selector"  # 添加唯一的key
            )
            current_index = video_ids.index(current_id)
            st.session_state.current_index = current_index

            # 获取当前视频片段
            item = config['main'][current_index]

            # 显示当前视频片段的内容
            st.subheader(f"当前预览: {item['id']}")
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                song_name, song_level, song_type = item['achievement_title'].split('-')
                st.text(f"谱面名称：{song_name}")
            with info_col2:
                st.text(f"谱面确认：({song_type}) {song_level}")
            main_col1, main_col2 = st.columns(2)
            with main_col1:
                st.image(item['main_image'], caption="成绩图片")
            with main_col2:
                st.video(item['video'])
                # TODO：添加修改视频的按钮
            item['text'] = st.text_area("评论", value=item.get('text', ''), key=f"text_{item['id']}")
            
            # 开始时间的分钟和秒输入
            st.write("开始时间：")
            time_col1, time_col2 = st.columns(2)
            with time_col1:
                current_minutes = int(item.get('start', 0) // 60)
                minutes = st.number_input("分钟", 
                                        min_value=0, 
                                        value=current_minutes,
                                        key=f"minutes_{item['id']}")
            with time_col2:
                current_seconds = int(item.get('start', 0) % 60)
                seconds = st.number_input("秒", 
                                        min_value=0,
                                        max_value=59, 
                                        value=current_seconds,
                                        key=f"seconds_{item['id']}")
            
            # 计算总秒数并更新item['start']
            item['start'] = minutes * 60 + seconds
            
            item['duration'] = st.number_input("持续时间（秒）", 
                                             min_value=1,
                                             max_value=60,
                                             value=item.get('duration', 15),
                                             key=f"duration_{item['id']}")

            # 上一个和下一个按钮
            col1, col2, _ = st.columns([1, 1, 2])
            with col1:
                if st.button("上一个"):
                    if st.session_state.current_index > 0:
                        # 保存当前配置
                        save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                        st.success("配置已保存！")
                        # 切换到上一个视频片段
                        st.session_state.current_index -= 1
                        st.session_state.dummy = str(time.time())  # 更新 session_state 以触发刷新
            with col2:
                if st.button("下一个"):
                    if st.session_state.current_index < len(video_ids) - 1:
                        # 保存当前配置
                        save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                        st.success("配置已保存！")
                        # 切换到下一个视频片段
                        st.session_state.current_index += 1
                        st.session_state.dummy = str(time.time())  # 更新 session_state 以触发刷新
                    else:
                        st.warning("已经是最后一个视频片段！")

            # 保存配置按钮
            if st.button("保存配置"):
                save_config(f"./b50_datas/video_configs_{G_config['USER_ID']}.json", config)
                st.success("配置已保存！")

    else:
        st.header("Step 3: 视频生成")
        if st.button("开始生成视频"):
            with st.spinner("正在生成视频..."):
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # 这里调用你的视频生成函数（main_gen.py）
                    subprocess.run(["python", "main_gen.py"])
                    st.success("视频生成完成！")
                except Exception as e:
                    st.error(f"生成失败: {str(e)}")

if __name__ == "__main__":
    main()
