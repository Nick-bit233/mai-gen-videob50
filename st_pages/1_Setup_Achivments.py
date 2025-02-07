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
from utils.dxnet_extension import get_rate
import glob

def convert_old_files(folder, username, save_paths):
    """
    遍历文件夹下的所有json文件，将文件名中包含用户名的旧文件名转换为不包含用户名的格式。
    例如，将 "xxx_xxx_{username}_xxx.json" 重命名为 "xxx_xxx_xxx.json"。
    """
    files_to_rename = []
    patterns = [
        f"*_{username}_*.json",
        f"{username}_*.json",
        f"*_{username}.json"
    ]
    
    for pattern in patterns:
        files_to_rename.extend(glob.glob(os.path.join(folder, pattern)))
    
    files_to_rename = list(set(files_to_rename))  # 去重
    if not files_to_rename:
        print("未找到需要转换的文件。")

    for old_filename in files_to_rename:
        basename = os.path.basename(old_filename)
        # 移除.json后缀
        name_without_ext = os.path.splitext(basename)[0]
        
        # 直接替换文件名中的用户名部分
        if name_without_ext.endswith(f"_{username}"):
            new_name = name_without_ext[:-len(f"_{username}")]
        elif name_without_ext.startswith(f"{username}_"):
            new_name = name_without_ext[len(f"{username}_"):]
        else:
            new_name = name_without_ext.replace(f"_{username}_", "_")
        
        # 添加回.json后缀
        new_name = f"{new_name}.json"
        new_filename = os.path.join(folder, new_name)
        
        if new_filename != old_filename:
            os.rename(old_filename, new_filename)
            print(f"重命名完成: {basename} -> {new_name}")
        else:
            print(f"跳过文件: {basename} (无需修改)")
    st.success("文件名转换完成！")

    # 修改video_configs文件中的image path
    video_config_file = save_paths['video_config']
    print(video_config_file)
    if not os.path.exists(video_config_file):
        st.error("未找到video_config文件！请检查是否已将完整旧版数据文件复制到新的文件夹！")
        return
    try:
        video_config = load_config(video_config_file)
        main_clips = video_config['main']
        for each in main_clips:
            id = each['id']
            __image_path = os.path.join(save_paths['image_dir'], id + ".png")
            __image_path = os.path.normpath(__image_path)
            each['main_image'] = __image_path
        save_config(video_config_file, video_config)          
        st.success("配置信息转换完成！")
    except Exception as e:
        st.error(f"转换video_config文件时发生错误: {e}")

@st.dialog("手动修改b50数据", width="large")
def edit_b50_data(user_id, save_id):
    save_paths = get_data_paths(user_id, save_id)
    datafile_path = save_paths['data_file']
    data = load_config(datafile_path)
    # get dx rating from raw data file
    raw_datafile_path = save_paths['raw_file']
    with open(raw_datafile_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        dx_rating = raw_data.get("rating", 0)
    st.markdown(f'【当前存档信息】\n \n - 用户名：{user_id} \n \n - <p style="color: #00BFFF;">存档ID(时间戳)：{save_id}</p> \n \n - <p style="color: #ffc107;">DX Rating：{dx_rating}</p>', unsafe_allow_html=True)
    st.warning("您可以在下方表格中修改本存档的b50数据，注意修改保存后将无法撤销！")
    st.info("水鱼查分器不返回游玩次数数据，如需在视频中展示请手动填写游玩次数。")
    
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
            "song_id": "曲ID",
            "title": "曲名",
            "type": st.column_config.SelectboxColumn(
                "类型",
                options=["SD", "DX"],
                width=40,
                required=True
            ),
            "level_label": st.column_config.SelectboxColumn(
                "难度",
                options=["Basic", "Advanced", "Expert", "Master", "Re:MASTER"],
                width=60,
                required=True
            ),
            "ds": st.column_config.NumberColumn(
                "定数",
                min_value=1.0,
                max_value=15.0,
                format="%.1f",
                width=60,
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
                "Fc标",
                options=["", "fc", "fcp", "ap", "app"],
                width=40,
                required=False
            ),
            "fs": st.column_config.SelectboxColumn(
                "Sync标",
                options=["", "sync", "fs", "fsp", "fsd", "fsdp"],
                width=40,
                required=False
            ),
            "ra": st.column_config.NumberColumn(
                "单曲Ra",
                format="%d",
                width=75,
                required=True
            ),
            "dxScore": st.column_config.NumberColumn(
                "DX分数",
                format="%d",
                width=75,
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
        # print(f"level_label: {record['level_label']} | level_index: {record['level_index']}")

        # 计算level
        # 将record['ds']切分为整数部分和小数部分
        ds_l, ds_p = str(record['ds']).split('.')
        # ds_p取第一位整数
        ds_p = int(ds_p[0])
        plus = '+' if ds_p > 6 else ''
        record['level'] = f"{ds_l}{plus}"
        # print(f"ds: {record['ds']} | level: {record['level']}")

        # 计算rate
        record['rate'] = get_rate(record['achievements'])
        # print(f"achievements: {record['achievements']} | rate: {record['rate']}")
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

st.header("获取或管理B50成绩存档")

def check_username(input_username):
    # 检查用户名是否包含非法字符
    if any(char in input_username for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        return remove_invalid_chars(input_username), input_username
    else:
        return input_username, input_username
    
def read_raw_username(username):
    raw_username_file = os.path.join(get_user_base_dir(username), "raw_username.txt")
    if os.path.exists(raw_username_file):
        with open(raw_username_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    else:
        return username

username = st.session_state.get("username", None)
save_id = st.session_state.get('save_id', None)
with st.container(border=True):
    input_username = st.text_input(
        "输入水鱼查分器用户名（国服查询）或一个您喜欢的用户名（国际服）",
        value=username if username else ""
    )

    if st.button("确定"):
        if not input_username:
            st.error("用户名不能为空！")
            st.session_state.config_saved = False
        else:  
            # 输入的username作为文件夹路径，需要去除非法字符
            # raw_username为注册查分器使用的用户名，除非用户名中包含非法字符，否则与username相同
            username, raw_username = check_username(input_username)
            root_save_dir = get_user_base_dir(username)
            if not os.path.exists(root_save_dir):
                os.makedirs(root_save_dir, exist_ok=True)
            # 创建一个文本文件用于保存raw_username
            raw_username_file = os.path.join(root_save_dir, "raw_username.txt")
            if not os.path.exists(raw_username_file):
                with open(raw_username_file, 'w', encoding='utf-8') as f:
                    f.write(raw_username)
            st.success("用户名已保存！")
            st.session_state.username = username  # 保存用户名到session_state
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

def update_b50(update_function, username, save_paths):
    try:
        # 新建存档文件夹
        os.makedirs(os.path.dirname(save_paths['raw_file']), exist_ok=True)
        b50_data = update_function(save_paths['raw_file'], save_paths['data_file'], username)
        st.success(f"已获取用户{username}的最新B50数据！新的存档时间为：{os.path.dirname(save_paths['data_file'])}")
        st.session_state.data_updated_step1 = True
        return b50_data
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"获取B50数据时发生错误: {e}")
        st.error(traceback.format_exc())
        return None

def check_save_available(username, save_id):
    if not save_id:
        return False
    save_paths = get_data_paths(username, save_id)
    return os.path.exists(save_paths['data_file'])

@st.dialog("从HTML源码导入数据", width="large")
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

@st.dialog("删除存档确认")
def delete_save_data(username, save_id):
    version_dir = get_user_version_dir(username, save_id)
    st.warning(f"是否确认删除存档：{username} - {save_id}？此操作将清除所有已生成的b50图片和视频文件，且不可撤销！")
    if st.button("确认删除"):
        # 迭代地删除文件夹version_dir下的所有文件和子文件夹
        for root, dirs, files in os.walk(version_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(version_dir)
        st.toast(f"已删除存档！{username} - {save_id}")
        st.rerun()
    if st.button("取消"):
        st.rerun()

# 仅在配置已保存时显示"开始预生成"按钮
if st.session_state.get('config_saved', False):
    raw_username = read_raw_username(username)

    st_init_cache_pathes()

    st.write("b50数据编辑")
    if st.button("查看和修改当前存档的b50数据", key="edit_b50_data"):
        save_id = st.session_state.get('save_id', None)
        save_available = check_save_available(username, save_id)
        if save_available:
            edit_b50_data(username, save_id)
        else:
            st.error("未找到b50数据，请先读取存档，或生成新存档！")

    st.write("b50存档读取")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            st.write(f"新获取的存档可能无法立刻显示在下拉栏中，单击任一其他存档即可进行刷新。")
            selected_save_id = st.selectbox(
                "选择存档",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("加载存档b50数据"):
                    if selected_save_id:
                        print(selected_save_id)
                        st.session_state.save_id = selected_save_id
                        st.success(f"已加载存档！用户名：{username}，存档时间：{selected_save_id}，可使用上方按钮加载和修改数据。")
                        st.session_state.data_updated_step1 = True                
                    else:
                        st.error("未指定有效的存档路径！")
            with col2:
                if st.button("打开存档文件夹"):
                    version_dir = get_user_version_dir(username, selected_save_id)
                    if os.path.exists(version_dir):
                        absolute_path = os.path.abspath(version_dir)
                    else:
                        absolute_path = os.path.abspath(os.path.dirname(version_dir))
                    open_file_explorer(absolute_path)
            with col3:
                if st.button("删除存档"):
                    delete_save_data(username, selected_save_id)
    else:
        st.warning(f"{username}还没有历史存档，请从下方获取新的B50数据。")

    st.write(f"新建b50存档")
    with st.container(border=True):
        st.info(f"使用下方的按钮，您将以用户名{raw_username}从查分器或HTML源码获取一份新的B50数据，系统将为您创建一份新的存档。")

        if st.button("从水鱼获取B50数据（国服）"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_id = os.path.basename(os.path.dirname(current_paths['data_file']))  # 从存档路径得到新存档的时间戳
            if save_id:
                st.session_state.save_id = save_id
                with st.spinner("正在获取B50数据更新..."):
                    update_b50(
                        update_b50_data,
                        raw_username,
                        current_paths,
                    )
        
        st.info("如您使用国际服数据，请先点击下方左侧按钮导入源代码，再使用下方右侧按钮读取数据。国服用户请忽略。")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("导入B50数据源代码"):
                input_html_data()
        
        with col2:
            if st.button("从本地HTML读取B50（国际服）"):
                current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
                save_id = os.path.basename(os.path.dirname(current_paths['data_file']))  # 从存档路径得到新存档的时间戳
                if save_id:
                    st.session_state.save_id = save_id
                    with st.spinner("正在读取HTML数据..."):
                        current_paths = update_b50(
                            update_b50_data_int,
                            username,
                            current_paths
                        )

    if st.session_state.get('data_updated_step1', False):
        st.write("确认你的B50数据无误后，请点击进行下一步按钮开始进行视频生成准备。")
        if st.button("进行下一步"):
            st.switch_page("st_pages/Generate_Pic_Resources.py")

    st.divider()

    with st.expander("从旧版本（v0.3.4及以下）迁移存档"):
        st.info("如果您之前使用过旧版本的B50视频生成器，按照顺序执行以下步骤以转移存档。")
        
        st.markdown("1. 点击下方按钮生成一份空白存档。")
        if st.button("新建空白存档"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_id = os.path.basename(os.path.dirname(current_paths['data_file']))  # 从存档路径得到新存档的时间戳
            os.makedirs(os.path.dirname(current_paths['raw_file']), exist_ok=True)
            st.session_state.save_id = save_id
            st.success(f"已新建空白存档！用户名：{username}，存档时间：{save_id}。")

        st.markdown(f"2. 点击下方按钮打开存档文件夹。请前往旧版本生成器的`b50_datas`目录，找到其中所有含有当前用户名`{username}`的`.json`文件，并将它们复制到新的存档目录中。")
        save_loaded = check_save_available(username, st.session_state.get('save_id', None))
        if not save_loaded:
            st.warning("未加载任何存档，请先加载或新建空白存档！")
        if st.button("打开存档文件夹", key="migrate_open_save_dir", disabled=not save_loaded):
            version_dir = get_user_version_dir(username, st.session_state.save_id)
            absolute_path = os.path.abspath(version_dir)
            open_file_explorer(absolute_path)

        st.markdown("3. 复制完成后，点击下方按钮将旧版数据文件转换为新版本。")
        if st.button("转换存档数据", disabled=not save_loaded):
            current_paths = get_data_paths(username, st.session_state.save_id)
            version_dir = get_user_version_dir(username, st.session_state.save_id)
            convert_old_files(version_dir, username, current_paths)
        
        st.markdown("4. 点击下方按钮打开视频下载目录。请前往旧版本生成器的`videos\downloads`目录，将已下载的视频文件复制到新的目录。如果还没有下载任何视频文件，可以跳过此步骤。")
        if st.button("打开视频下载目录"):
            open_file_explorer(os.path.abspath("./videos/downloads"))
        
        st.markdown("5. 完成上述步骤后，请回到页面上方，点击“查看和修改当前存档的b50数据”按钮，检查存档数据是否正常。**图片文件不会迁移，您仍需进入下一步重新生成图片文件**。如果您已经完成了下载视频的迁移，在图片生成后可以直接跳转第4步进行内容编辑。")
else:
    st.warning("请先确定用户名！")
