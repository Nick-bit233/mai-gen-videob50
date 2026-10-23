import streamlit as st
from utils.app_version import APP_VERSION
from utils.diagnostics import diagnostic_scope, current_report, install_streamlit_error_capture
from utils.metadata_release import metadata_snapshot
install_streamlit_error_capture()

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


setup_page = st.Page("st_pages/Setup_Achievements.py",
                title="获取/管理查分器数据",
                icon=":material/leaderboard:",
                url_path="setup")
custom_setup_page = st.Page("st_pages/Make_Custom_Save.py",
                title="编辑数据/创建自定义数据",
                icon=":material/leaderboard:",
                url_path="custom")
img_gen_page = st.Page("st_pages/Generate_Pic_Resources.py",
                title="1. 生成成绩图片",
                icon=":material/photo_library:",
                url_path="img_gen")
search_page = st.Page("st_pages/Search_For_Videos.py",
                title="2. 匹配谱面确认视频信息",
                icon=":material/video_search:",
                url_path="search")
download_page = st.Page("st_pages/Confirm_Videos.py",
                title="3. 检查和下载视频",
                icon=":material/video_settings:",
                url_path="download")
edit_comment_page = st.Page("st_pages/Edit_Video_Content.py",
                title="4-1. 编辑视频片段",
                icon=":material/movie_edit:",
                url_path="edit")
edit_intro_ending_page = st.Page("st_pages/Edit_OpEd_Content.py",
                title="4-2. 编辑开场和结尾片段",
                icon=":material/edit_note:",
                url_path="edit_oped")
composite_page = st.Page("st_pages/Composite_Videos.py",
                title="5. 合成视频",
                icon=":material/animated_images:",
                url_path="composite")
report_page = st.Page("st_pages/Error_Reports.py", title="错误报告与硬件检查",
                      icon=":material/bug_report:", url_path="reports")

pg = st.navigation(
    {
        "首页": [homepage, custom_video_style, report_page],
        "数据管理": [
            setup_page,
            custom_setup_page,
        ],
        "资源生成":[
            img_gen_page,
            search_page,
            download_page,
        ],
        "评论编辑":[
            edit_comment_page,
            edit_intro_ending_page
        ],
        "合成视频": [composite_page],
    }
)

with diagnostic_scope(), metadata_snapshot():
    try:
        pg.run()
    finally:
        report = current_report(create=False)
        if report:
            st.session_state['last_diagnostic_report'] = report.report_id
