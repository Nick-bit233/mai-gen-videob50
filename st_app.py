import streamlit as st

homepage = st.Page("st_pages/0_homepage.py",
                title="首页",
                icon=":material/home:")
setup = st.Page("st_pages/1_Setup_Achivments.py",
                title="1. 获取B50成绩",
                icon=":material/leaderboard:")
search = st.Page("st_pages/2_Search_For_Videoes.py",
                title="2. 搜索谱面确认视频信息",
                icon=":material/video_search:")
download = st.Page("st_pages/3_Confrim_Videoes.py",
                title="3. 检查和下载视频",
                icon=":material/video_settings:")
edit_comment = st.Page("st_pages/4_Edit_Video_Content.py",
                title="4-1. 编辑B50视频片段",
                icon=":material/movie_edit:")
edit_intro_ending = st.Page("st_pages/5_Edit_OpEd_Content.py",
                title="4-2. 编辑开场和结尾片段",
                icon=":material/edit_note:")
composite = st.Page("st_pages/6_Compostie_Videoes.py",
                title="5. 合成视频",
                icon=":material/animated_images:")

pg = st.navigation(
    {
        "Home": [homepage],
        "Pre-generation": [setup, search, download],
        "Edit-video": [edit_comment, edit_intro_ending],
        "Run-generation": [composite]
    }
)

pg.run()
