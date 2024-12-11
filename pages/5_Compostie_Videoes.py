import streamlit as st
import subprocess

st.header("Step 5: 视频生成")
if st.button("开始生成视频"):
    with st.spinner("正在生成视频..."):
        st.write("代码迁移施工中...")
        # 创建进度条
        # progress_bar = st.progress(0)
        # status_text = st.empty()
        
        # try:
        #     # 这里调用你的视频生成函数（main_gen.py）
        #     subprocess.run(["python", "main_gen.py"])
        #     st.success("视频生成完成！")
        # except Exception as e:
        #     st.error(f"生成失败: {str(e)}")
if st.button("终止"):
    st.stop()
