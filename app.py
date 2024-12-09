import streamlit as st
import os
import json
import subprocess
from PIL import Image
import time

def load_config(config_file):
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_config(config_file, config_data):
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

def main():
    st.set_page_config(page_title="Mai-gen Videob50", layout="wide")
    
    st.title("Mai-gen Videob50 视频生成器")
    
    # 侧边栏：步骤导航
    with st.sidebar:
        st.header("处理步骤")
        step = st.radio(
            "选择当前步骤",
            ["1. 数据获取和视频下载", "2. 配置编辑", "3. 视频生成"]
        )
    
    if step == "1. 数据获取和视频下载":
        st.header("Step 1: 数据获取和视频下载")
        
        # 配置输入
        username = st.text_input("输入水鱼查分器用户名")
        if st.button("开始下载"):
            with st.spinner("正在获取数据和下载视频..."):
                # 创建进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 执行下载过程（使用你现有的pre_gen.py代码）
                try:
                    # 这里调用你的下载函数，并通过回调更新进度
                    subprocess.run(["python", "pre_gen.py", username])
                    st.success("下载完成！")
                except Exception as e:
                    st.error(f"下载失败: {str(e)}")

    elif step == "2. 配置编辑":
        st.header("Step 2: 配置编辑")
        
        # 加载配置文件
        config = load_config(f"./b50_datas/video_configs_{st.session_state.get('username', '')}.json")
        if config:
            # 创建三列布局
            col1, col2, col3 = st.columns([2, 2, 1])
            
            for item in config['main']:
                with st.container():
                    st.subheader(f"编号: {item['id']} - {item['achievement_title']}")
                    
                    # 第一列：显示成绩图片
                    with col1:
                        st.image(item['main_image'], caption="成绩图片")
                    
                    # 第二列：显示视频预览
                    with col2:
                        st.video(item['video'])
                    
                    # 第三列：编辑配置
                    with col3:
                        item['text'] = st.text_area("评论", value=item.get('text', ''), key=f"text_{item['id']}")
                        item['start'] = st.number_input("开始时间", value=item.get('start', 0), key=f"start_{item['id']}")
                        item['duration'] = st.number_input("持续时间", value=item.get('duration', 15), key=f"duration_{item['id']}")
            
            if st.button("保存配置"):
                save_config(f"./b50_datas/video_configs_{st.session_state.get('username', '')}.json", config)
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
