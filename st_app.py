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

# 刷新/重启后恢复上次使用的用户名、游戏类型和对应存档。
if not st.session_state.get("username"):
    from utils.user_preferences import load_saved_user
    saved_username, saved_safe_username = load_saved_user()
    if saved_username:
        st.session_state.username = saved_username
        st.session_state.safe_username = saved_safe_username or saved_username
        # 恢复的用户名视为已完成用户设置，Setup 页面可直接进入存档管理。
        st.session_state.config_saved = True
elif st.session_state.get("username"):
    st.session_state.setdefault("config_saved", True)

if not st.session_state.get("game_type"):
    from utils.user_preferences import load_user_preferences
    st.session_state.game_type = load_user_preferences().get(
        "last_game_type", "maimai")

if st.session_state.get("username") and not st.session_state.get("archive_id"):
    try:
        from utils.user_preferences import load_saved_archive
        from db_utils.DatabaseDataHandler import get_database_handler

        restore_username = st.session_state.username
        restore_game_type = st.session_state.get("game_type", "maimai")
        restore_db = get_database_handler()
        restore_archives = restore_db.get_user_save_list(
            restore_username, game_type=restore_game_type)
        restore_archives.sort(
            key=lambda item: item.get("created_at") or "", reverse=True)
        saved_archive = load_saved_archive(restore_username, restore_game_type)
        target = next(
            (item for item in restore_archives
             if item.get("archive_name") == saved_archive),
            None,
        )
        if target is None and restore_archives:
            # 记录里的存档已被删除时，退回该游戏类型下最新的存档。
            target = restore_archives[0]
        if target:
            target_name = target.get("archive_name")
            target_id = restore_db.load_save_archive(restore_username, target_name)
            if target_id:
                st.session_state.archive_id = target_id
                st.session_state.archive_name = target_name
                archive_meta = restore_db.load_archive_metadata(
                    restore_username, target_name)
                if archive_meta:
                    st.session_state.archive_meta = archive_meta
    except Exception:
        pass

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
        # 页面切换/刷新前记住当前存档，下一次自动恢复。
        try:
            from utils.user_preferences import save_archive
            from db_utils.DatabaseDataHandler import get_database_handler
            persist_username = st.session_state.get("username")
            persist_game_type = st.session_state.get("game_type")
            persist_archive = st.session_state.get("archive_name")
            if persist_username and persist_game_type and persist_archive:
                # 只记录确实属于当前用户名的存档，避免切换用户名后串档。
                if get_database_handler().load_save_archive(
                        persist_username, persist_archive):
                    save_archive(persist_username, persist_game_type, persist_archive)
        except Exception:
            pass
        report = current_report(create=False)
        if report:
            st.session_state['last_diagnostic_report'] = report.report_id
