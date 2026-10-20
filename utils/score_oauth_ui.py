"""Streamlit authorization and snapshot selection; no tokens in widget state."""
import streamlit as st

from utils.score_oauth import OAuthError, load_public_config, start_oauth
from utils.score_selection import select_scores


@st.fragment(run_every=1)
def _await_authorization(flow, key):
    if flow.status not in ("awaiting_authorization", "fetching"):
        st.rerun()
    if flow.status == "awaiting_authorization":
        st.link_button("打开查分器授权页面", flow.authorization_url, type="primary")
        st.info("请在运行视频生成器的这台电脑上完成授权。完成后返回本页，成绩会自动加载。")
    else:
        st.info("授权已收到，正在读取全部成绩和谱面版本信息……")
    if st.button("取消本次授权", key=f"{key}_cancel"):
        flow.cancel()
        st.session_state.pop(key, None)
        st.rerun()


def render_score_oauth(provider, game_type, username, save_archive):
    key = f"score_oauth_{provider}"
    flow = st.session_state.get(key)
    if flow and (flow.owner != username or flow.game_type != game_type):
        flow.cancel()
        st.session_state.pop(key, None)
        st.session_state.pop(f"{key}_selection", None)
        flow = None
    st.caption("先授权读取全部成绩，再选择分表。用户名仅用于本地存档管理。")
    try:
        default_id, default_port = load_public_config(provider)
    except OAuthError as exc:
        st.error(str(exc))
        return
    with st.popover("OAuth 应用配置"):
        client_id = st.text_input("公开客户端 client_id", value=default_id, key=f"{key}_client_id",
                                  help="由开源版维护者登记的 OAuth 应用 ID，可公开分发。")
        port = st.number_input("本机回调端口", min_value=1024, max_value=65535,
                               value=default_port, step=1, key=f"{key}_port")
        st.code(f"http://127.0.0.1:{port}/callback", language=None)
        st.caption("此回调地址须在查分器应用后台登记。配置方法见 docs/OAuthGuide.md。")
    if not client_id.strip():
        st.info("此安装包尚未配置查分器应用 ID，请在“OAuth 应用配置”中填写维护者提供的公开客户端 ID。")
    if flow is None or flow.status in ("failed", "cancelled"):
        if flow and flow.error:
            st.error(flow.error)
        if st.button("授权并获取全部成绩", key=f"{key}_start", type="primary", disabled=not client_id.strip()):
            try:
                if flow:
                    flow.cancel()
                with st.spinner("准备授权……"):
                    st.session_state[key] = start_oauth(provider, game_type, username, client_id, port)
                st.rerun()
            except OAuthError as exc:
                st.error(str(exc))
        return
    if flow.status in ("awaiting_authorization", "fetching"):
        _await_authorization(flow, key)
        return
    if flow.status != "ready" or flow.snapshot is None:
        return
    snapshot = flow.snapshot
    st.success(f"已获取全部成绩，共 {len(snapshot.payload['records'])} 条。")
    modes = ["b50", "apb50"] if game_type == "maimai" else ["b50"]
    mode = st.radio("筛选分表", modes, index=0, horizontal=True, key=f"{key}_selection",
                    format_func=lambda value: "AP B50（AP/AP+，最多 50 谱）" if value == "apb50" else "B50（默认）")
    st.caption("B50：旧曲 35 + 新曲 15。AP B50：跨版本选取 AP/AP+，按单曲 Rating 排序，最多 50 谱。"
               if game_type == "maimai" else "中二节奏：旧曲 B30 + 新曲 N20。")
    try:
        rows = select_scores(snapshot, mode)
        st.write(f"当前筛选：{len(rows)} 个谱面。")
        st.dataframe([{"抬头": row["clip_title_name"], "曲名": row.get("title", row.get("song_name")),
                       "难度": row.get("level_index"), "定数": row.get("ds"),
                       "成绩": row.get("achievements", row.get("score")),
                       "AP/FC": row.get("fc", row.get("full_combo")),
                       "Rating": row.get("ra", row.get("dx_rating", row.get("rating")))} for row in rows],
                      hide_index=True, use_container_width=True)
        if st.button("将所选分表保存为新存档", key=f"{key}_save", type="primary"):
            save_archive(username, source=provider, params={"type": game_type, "selection": mode,
                                                         "oauth_snapshot": snapshot})
    except OAuthError as exc:
        st.warning(str(exc))
    if st.button("重新授权 / 切换查分器账号", key=f"{key}_reset"):
        flow.cancel()
        st.session_state.pop(key, None)
        st.session_state.pop(f"{key}_selection", None)
        st.rerun()
