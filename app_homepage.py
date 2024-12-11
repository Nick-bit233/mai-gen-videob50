import streamlit as st

st.set_page_config(
    page_title="Hello",
    page_icon="👋",
    layout="wide"
)

st.title("Mai-gen Videob50 视频生成器 - 欢迎")

st.markdown(
    """
    详细使用说明请参考：
    [Github](https://github.com/Nick-bit233/mai-gen-videob50)
    """)

st.write("单击下面的按钮开始使用")

if st.button("开始使用"):
    st.switch_page("pages/1_Setup_Achivments.py")
