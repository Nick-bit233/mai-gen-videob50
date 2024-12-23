import streamlit as st
from utils.PageUtils import change_theme
from utils.themes import THEME_COLORS

st.title("Mai-gen Videob50 视频生成器")

st.write("当前版本: v0.3.2")

st.markdown(
    """
    请按照下列引导步骤操作，以生成您的B50视频。

    详细使用说明请参考：[Github](https://github.com/Nick-bit233/mai-gen-videob50)
    """)

st.info("在使用过程中，请不要随意刷新页面。如果因为误刷新页面导致下载器缓存丢失，请回到第1步重新开始操作。")
st.info("如果你已经运行过本应用并完成了1-3步，可以从左侧选项卡中直接跳转到4-5步以编辑评论或直接开始生成视频。")
st.success("使用过程中遇到任何问题，可以前往Github页面发起issue，或加入QQ群：994702414 反馈")

st.write("单击下面的按钮开始")

if st.button("开始使用"):
    st.switch_page("st_pages/1_Setup_Achivments.py")

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
