import streamlit as st

# 设置应用标题
st.set_page_config(
    page_title="mai-chu分表视频生成器",
    page_icon="🎵",
    layout="wide"
)

homepage = st.Page("st_pages/Homepage.py",
                title="首页",
                icon=":material/home:",
                default=True)
custom_video_style = st.Page("st_pages/Custom_Video_Style_Config.py",
                title="自定义视频模板",
                icon=":material/format_paint:")

# B30 (中二侧 - chunithm) 相关页面
setup_b30 = st.Page("st_pages/Setup_Achievements.py",
                title="获取/管理查分器B30数据",
                icon=":material/leaderboard:",
                url_path="b30_setup")
custom_setup_b30 = st.Page("st_pages/Make_Custom_Save.py",
                title="编辑B30数据/创建自定义B30数据",
                icon=":material/leaderboard:",
                url_path="b30_custom")
img_gen_b30 = st.Page("st_pages/Generate_Pic_Resources.py",
                title="1. 生成B30成绩图片",
                icon=":material/photo_library:",
                url_path="b30_img_gen")
search_b30 = st.Page("st_pages/Search_For_Videos.py",
                title="2. 搜索谱面确认视频信息",
                icon=":material/video_search:",
                url_path="b30_search")
download_b30 = st.Page("st_pages/Confirm_Videos.py",
                title="3. 检查和下载视频",
                icon=":material/video_settings:",
                url_path="b30_download")
edit_comment_b30 = st.Page("st_pages/Edit_Video_Content.py",
                title="4-1. 编辑B30视频片段",
                icon=":material/movie_edit:",
                url_path="b30_edit")
edit_intro_ending_b30 = st.Page("st_pages/Edit_OpEd_Content.py",
                title="4-2. 编辑开场和结尾片段",
                icon=":material/edit_note:",
                url_path="b30_edit_oped")
composite_b30 = st.Page("st_pages/Composite_Videos.py",
                title="5. 合成视频",
                icon=":material/animated_images:",
                url_path="b30_composite")

# B50 (maimai侧) 相关页面
setup_b50 = st.Page("st_pages/Setup_Achievements.py",
                title="获取/管理查分器B50数据",
                icon=":material/leaderboard:",
                url_path="b50_setup")
custom_setup_b50 = st.Page("st_pages/Make_Custom_Save.py",
                title="编辑B50数据/创建自定义B50数据",
                icon=":material/leaderboard:",
                url_path="b50_custom")
img_gen_b50 = st.Page("st_pages/Generate_Pic_Resources.py",
                title="1. 生成B50成绩图片",
                icon=":material/photo_library:",
                url_path="b50_img_gen")
search_b50 = st.Page("st_pages/Search_For_Videos.py",
                title="2. 搜索谱面确认视频信息",
                icon=":material/video_search:",
                url_path="b50_search")
download_b50 = st.Page("st_pages/Confirm_Videos.py",
                title="3. 检查和下载视频",
                icon=":material/video_settings:",
                url_path="b50_download")
edit_comment_b50 = st.Page("st_pages/Edit_Video_Content.py",
                title="4-1. 编辑B50视频片段",
                icon=":material/movie_edit:",
                url_path="b50_edit")
edit_intro_ending_b50 = st.Page("st_pages/Edit_OpEd_Content.py",
                title="4-2. 编辑开场和结尾片段",
                icon=":material/edit_note:",
                url_path="b50_edit_oped")
composite_b50 = st.Page("st_pages/Composite_Videos.py",
                title="5. 合成视频",
                icon=":material/animated_images:",
                url_path="b50_composite")

pg = st.navigation(
    {
        "首页": [homepage, custom_video_style],
        "B30": [
            setup_b30,
            custom_setup_b30,
            img_gen_b30,
            search_b30,
            download_b30,
            edit_comment_b30,
            edit_intro_ending_b30,
            composite_b30
        ],
        "B50": [
            setup_b50,
            custom_setup_b50,
            img_gen_b50,
            search_b50,
            download_b50,
            edit_comment_b50,
            edit_intro_ending_b50,
            composite_b50
        ]
    }
)

pg.run()
