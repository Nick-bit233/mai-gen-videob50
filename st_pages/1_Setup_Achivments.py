import streamlit as st
import os
import json
import subprocess
import traceback
from copy import deepcopy
from datetime import datetime
from pre_gen import update_b50_data, st_init_cache_pathes
from pre_gen_int import update_b50_data_int
from gene_images import generate_single_image, check_mask_waring
from utils.PageUtils import *
from utils.PathUtils import *

def count_rate(acc):
    if acc >= 100.5:
        return "sssp"
    elif acc >= 100.0:
        return "sss"
    elif acc >= 99.5:
        return "ssp"
    elif acc >= 99.0:
        return "ss"
    elif acc >= 98.0:
        return "sp"
    elif acc >= 97.0:
        return "s"
    else:
        return "aaa"

@st.dialog("手动修改b50数据", width="large")
def edit_b50_data(user_id, save_paths):
    datafile_path = save_paths['data_file']
    data = load_config(datafile_path)
    save_id = os.path.basename(os.path.dirname(datafile_path))
    st.write(f"【当前存档】用户名：{user_id}，存档时间：{save_id} ")
    st.info("您可以在下方表格中修改本存档的b50数据，注意修改保存后将无法撤销！")
    
    # json数据中添加游玩次数字段
    for item in data:
        if "playCount" not in item:
            item["playCount"] = 0  # 设置默认值
    
    # 创建可编辑表格
    edited_df = st.data_editor(
        data,
        column_order=["clip_id", "song_id", "title", "type", "level_label",
                    "ds", "achievements", "fc", "fs", "ra", "dxScore", "playCount"],
        column_config={
            "clip_id": "编号",
            "song_id": "歌曲ID",
            "title": "曲名",
            "type": st.column_config.SelectboxColumn(
                "谱面类型",
                options=["SD", "DX"],
                required=True
            ),
            "level_label": st.column_config.SelectboxColumn(
                "谱面难度",
                options=["Basic", "Advanced", "Expert", "Master", "Re:MASTER"],
                required=True
            ),
            "ds": st.column_config.NumberColumn(
                "定数",
                min_value=1.0,
                max_value=15.0,
                format="%.1f",
                required=True
            ),
            "achievements": st.column_config.NumberColumn(
                "达成率",
                min_value=0.0,
                max_value=101.0,
                format="%.4f",
                required=True
            ),
            "fc": st.column_config.SelectboxColumn(
                "Combo标记",
                options=["", "fc", "fcp", "ap", "app"],
                required=False
            ),
            "fs": st.column_config.SelectboxColumn(
                "Sync标记",
                options=["", "sync", "fs", "fsp", "fsd", "fsdp"],
                required=False
            ),
            "ra": st.column_config.NumberColumn(
                "单曲Rating",
                format="%d",
                required=True
            ),
            "dxScore": st.column_config.NumberColumn(
                "DX分数",
                format="%d",
                required=True
            ),
            "playCount": st.column_config.NumberColumn(
                "游玩次数",
                format="%d",
                required=False
            )
        },
        disabled=["clip_id"],
        hide_index=False
    )
    
    # 根据填写数值自动计算其他字段
    for record in edited_df:
        # 计算level_index
        REVERSE_LEVEL_LABELS = {v: k for k, v in LEVEL_LABELS.items()}
        level_index = REVERSE_LEVEL_LABELS.get(record['level_label'].upper())
        record['level_index'] = level_index
        print(f"level_label: {record['level_label']} | level_index: {record['level_index']}")

        # 计算level
        # 将record['ds']切分为整数部分和小数部分
        ds_l, ds_p = str(record['ds']).split('.')
        # ds_p取第一位整数
        ds_p = int(ds_p[0])
        plus = '+' if ds_p > 6 else ''
        record['level'] = f"{ds_l}{plus}"
        print(f"ds: {record['ds']} | level: {record['level']}")

        # 计算rate
        record['rate'] = count_rate(record['achievements'])
        print(f"achievements: {record['achievements']} | rate: {record['rate']}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存修改"):
            # DataFrame is returned as JSON format list
            # json_data = edited_df
            with open(datafile_path, 'w', encoding='utf-8') as f:
                json.dump(edited_df, f, ensure_ascii=False, indent=2)
            st.success("更改已保存！")
    with col2:
        if st.button("结束编辑并返回"):
            st.rerun()

def show_b50_dataframe(info_placeholder, user_id, save_paths):
    with info_placeholder.container(border=True):
        datafile_path = save_paths['data_file']
        b50_data = load_config(datafile_path)
        save_id = os.path.basename(os.path.dirname(datafile_path))
        st.write(f"【当前存档】用户名：{user_id}，存档时间：{save_id} ")
        st.dataframe(b50_data, column_order=["clip_id", "title", "level_label", "level",  "ds", "achievements", "fc", "fs", "ra", "dxScore"])

st.header("Step 1: 配置生成器参数和B50成绩数据")

def check_username(input_username):
    # 检查用户名是否包含非法字符
    if any(char in input_username for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        return remove_invalid_chars(input_username), input_username
    else:
        return input_username, input_username

with st.container(border=True):
    G_config = read_global_config()
    raw_username = G_config.get('USER_ID_RAW', '')
    input_username = st.text_input("输入水鱼查分器用户名（国服查询）或一个您喜欢的用户名（国际服）", value=raw_username)

    if st.button("确定"):
        if not input_username:
            st.error("用户名不能为空！")
            st.session_state.config_saved = False
        else:  
            # 输入的username作为文件夹路径，需要去除非法字符
            # raw_username为查分器返回的用户名，除非用户名中包含非法字符，否则与username相同
            username, raw_username = check_username(input_username)
            # 更新配置字典
            G_config['USER_ID'] = username
            G_config['USER_ID_RAW'] = raw_username
            # 写入配置文件
            write_global_config(G_config)
            st.success("配置已保存！")
            st.session_state.config_saved = True  # 添加状态标记

def st_generate_b50_images(placeholder, user_id):
    b50_data_file = os.path.join(os.path.dirname(__file__), '..', 'b50_datas', f"b50_config_{user_id}.json")
    # read b50_data
    b50_data = load_config(b50_data_file)
    # make folder for user's b50_images
    os.makedirs(f"./b50_images/{user_id}", exist_ok=True)
    with placeholder.container(border=True):
        pb = st.progress(0, text="正在生成B50成绩背景图片...")
        mask_check_cnt = 0
        mask_warn = False
        warned = False
        for index, record_detail in enumerate(b50_data):
            pb.progress((index + 1) / len(b50_data), text=f"正在生成B50成绩背景图片({index + 1}/{len(b50_data)})")
            acc_string = f"{record_detail['achievements']:.4f}"
            mask_check_cnt, mask_warn = check_mask_waring(acc_string, mask_check_cnt, mask_warn)
            if mask_warn and not warned:
                st.warning("检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。特殊情况请忽略。")
                warned = True
            record_for_gene_image = deepcopy(record_detail)
            record_for_gene_image['achievements'] = acc_string
            prefix = "PastBest" if index < 35 else "NewBest"
            image_name_index = index if index < 35 else index - 35
            generate_single_image(
                "./images/B50ViedoBase.png",
                record_for_gene_image,
                user_id,
                prefix,
                image_name_index,
            )

def load_history_saves(placeholder, username, timestamp=None):
    try:
        paths = get_data_paths(username, timestamp)
        if os.path.exists(paths['data_file']):
            # b50_data = load_config(paths['data_file'])
            st.success("已加载历史配置")
            st.session_state.data_updated_step1 = True
            show_b50_dataframe(placeholder, username, paths)
            return paths
        else:
            st.warning("未找到历史配置")
            st.session_state.data_updated_step1 = False
            return None
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"获取配置时发生错误: {e}")
        st.error(traceback.format_exc())
        return None

def update_b50(placeholder, update_function, username, save_paths):
    try:
        # 新建存档文件夹
        os.makedirs(os.path.dirname(save_paths['raw_file']), exist_ok=True)
        b50_data = update_function(save_paths['raw_file'], save_paths['data_file'], username)
        st.success("已更新B50数据！")
        st.session_state.data_updated_step1 = True
        show_b50_dataframe(placeholder, username, save_paths)
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"获取B50数据时发生错误: {e}")
        st.error(traceback.format_exc())

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved', False):
    G_config = read_global_config()
    username = G_config.get('USER_ID', '')
    raw_username = G_config.get('USER_ID_RAW', '')
    image_path = f"./b50_images/{username}"

    st_init_cache_pathes()

    st.write("b50数据编辑")
    update_info_placeholder = st.empty()
    if st.button("手动修改当前存档的b50数据"):
        save_paths = st.session_state.get('current_paths', None)
        if save_paths:
            edit_b50_data(username, save_paths)
        else:
            st.error("尚未读取b50数据，请先读取存档，或生成新存档！")

    st.write("b50存档读取")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            selected_version = st.selectbox(
                "选择要加载的存档",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            if st.button("加载存档b50数据"):
                if selected_version:
                    print(selected_version)
                    current_paths = load_history_saves(
                        update_info_placeholder, 
                        username, 
                        selected_version
                    )
                    if current_paths:
                        st.session_state.current_paths = current_paths
                        st.session_state.data_loaded = True
                else:
                    st.error("未指定有效的存档路径！")
    else:
        st.warning(f"{username}还没有历史存档，请从下方获取最新的B50数据。")
    
    @st.dialog("从HTML源码导入数据")
    def input_html_data():
        st.info("请将复制的网页源代码粘贴到下方输入栏：")
        if os.path.exists(f"./{username}.html"):
            st.info(f"注意，重复导入将会覆盖已有html数据文件：{username}.html")
        html_input = st.text_area("html_input", height=600)
        if st.button("确认保存"):
            with open(f"./{username}.html", 'w', encoding="utf-8") as f:
                f.write(html_input)
                st.toast("HTML数据已保存！")
                st.rerun()

    st.write(f"新建b50存档")
    with st.container(border=True):
        st.info(f"使用下方的按钮，您将以用户名{raw_username}从查分器或HTML源码获取一份新的B50数据，系统将为您创建一份新的存档。")

        if st.button("从水鱼获取B50数据（国服）"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            if current_paths:
                print(current_paths)
                st.session_state.current_paths = current_paths
                with st.spinner("正在获取B50数据更新..."):
                    update_b50(
                        update_info_placeholder,
                        update_b50_data,
                        raw_username,
                        current_paths,
                    )
                st.session_state.data_loaded = True
        
        st.info("如您使用国际服数据，请先点击下方左侧按钮导入源代码，再使用下方右侧按钮读取数据。国服用户请忽略。")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("导入B50数据源代码"):
                # 参考水鱼做法使用dialog框架
                input_html_data()
        
        with col2:
            if st.button("从本地HTML读取B50（国际服）"):
                current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
                if current_paths:
                    print(current_paths)
                    st.session_state.current_paths = current_paths
                    with st.spinner("正在读取HTML数据..."):
                        current_paths = update_b50(
                            update_info_placeholder,
                            update_b50_data_int,
                            username,
                            current_paths
                        )
                    st.session_state.data_loaded = True

    if st.session_state.get('data_updated_step1', False):
        st.text("生成成绩背景图片")
        with st.container(border=True):
            st.write("确认你的B50数据无误后，请点击下面的按钮，生成成绩背景图片：")
            if st.button("生成成绩背景图片"):
                generate_info_placeholder = st.empty()
                try:
                    image_path = f"./b50_images/{username}"
                    os.makedirs(image_path, exist_ok=True)
                    st_generate_b50_images(generate_info_placeholder, username)
                    st.success("生成成绩背景图片完成！")
                except Exception as e:
                    st.error(f"生成成绩背景图片时发生错误: {e}")
                    st.error(traceback.format_exc())
            if os.path.exists(image_path):
                absolute_path = os.path.abspath(image_path)
            else:
                absolute_path = os.path.abspath(os.path.dirname(image_path))
            if st.button("打开成绩图片文件夹", key=f"open_folder_{username}"):
                open_file_explorer(absolute_path)
            st.info("如果你已经生成过背景图片，且无需更新，可以跳过，请点击进行下一步按钮。")
            if st.button("进行下一步"):
                st.switch_page("st_pages/2_Search_For_Videoes.py")

else:
    st.warning("请先确定配置！")  # 如果未保存配置，给出提示