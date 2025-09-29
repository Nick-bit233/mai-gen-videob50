import streamlit as st
import os
import json
import traceback
from datetime import datetime
from utils.user_gamedata_handlers import fetch_user_gamedata, update_b50_data_int
from utils.PageUtils import *
from utils.PathUtils import *
import glob

maimai_level_label_list = list(LEVEL_LABELS.values())

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
        video_config = load_video_config(video_config_file)
        main_clips = video_config['main']
        for each in main_clips:
            id = each['id']
            __image_path = os.path.join(save_paths['image_dir'], id + ".png")
            __image_path = os.path.normpath(__image_path)
            each['main_image'] = __image_path
        save_video_config(video_config_file, video_config)          
        st.success("配置信息转换完成！")
    except Exception as e:
        st.error(f"转换video_config文件时发生错误: {e}")

@st.dialog("b50数据查看", width="large")
def edit_b50_data(user_id, save_id):
    save_paths = get_data_paths(user_id, save_id)
    datafile_path = save_paths['data_file']
    with open(datafile_path, 'r', encoding='utf-8') as f:
        head_data = json.load(f)
        dx_rating = head_data.get("rating", 0)
        data = head_data.get("records", None)
    st.markdown(f'【当前存档信息】\n \n - 用户名：{user_id} \n \n - <p style="color: #00BFFF;">存档ID(时间戳)：{save_id}</p> \n \n - <p style="color: #ffc107;">DX Rating：{dx_rating}</p>', unsafe_allow_html=True)
    st.error("请注意：该页面组件已于v0.5.0版本后过时，如需手动修改存档，请在‘创建自定义B50存档’页面中操作。本窗口现为只读属性，无法保存数据修改！")
    st.info("水鱼查分器不返回游玩次数数据，如需在视频中展示请手动填写游玩次数。")

    st.dataframe(
        data,
        column_order=["clip_name", "song_id", "title", "type", "level_label",
                    "ds", "achievements", "fc", "fs", "ra", "dxScore", "playCount"],
        column_config={
            "clip_name": "抬头标题",
            "song_id": "曲ID",
            "title": "曲名",
            "type": st.column_config.TextColumn(
                "类型",
                width=40
            ),
            "level_label": st.column_config.TextColumn(
                "难度",
                width=60
            ),
            "ds": st.column_config.NumberColumn(
                "定数",
                min_value=1.0,
                max_value=15.0,
                format="%.1f",
                width=60
            ),
            "achievements": st.column_config.NumberColumn(
                "达成率",
                min_value=0.0,
                max_value=101.0,
                format="%.4f"
            ),
            "fc": st.column_config.TextColumn(
                "Fc标",
                width=40
            ),
            "fs": st.column_config.TextColumn(
                "Sync标",
                width=40
            ),
            "ra": st.column_config.NumberColumn(
                "单曲Ra",
                format="%d",
                width=75
            ),
            "dxScore": st.column_config.NumberColumn(
                "DX分数",
                format="%d",
                width=75
            ),
            "playCount": st.column_config.NumberColumn(
                "游玩次数",
                format="%d"
            )
        }
    )

    if st.button("返回"):
        st.rerun()

st.header("获取和管理B50成绩存档")

def check_username(input_username):
    ret_username = input_username
    # 检查用户名是否包含非法字符
    if any(char in input_username for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        ret_username = remove_invalid_chars(input_username)
    # 检查用户名中是否包含空格，将空格转换为下划线
    if ' ' in ret_username:
        ret_username = ret_username.replace(' ', '_')
    return ret_username, input_username
    
def read_raw_username(username):
    raw_username_file = os.path.join(get_user_base_dir(username), "raw_username.txt")
    if os.path.exists(raw_username_file):
        with open(raw_username_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return username

username = st.session_state.get("username", None)
save_id = st.session_state.get('save_id', None)
with st.container(border=True):
    input_username = st.text_input(
        "输入水鱼查分器用户名（国服查询）或一个您喜欢的用户名（其他数据源）",
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

def fetch_new_achievement_data(username, save_paths, source, params=None):
    save_timestamp = os.path.dirname(save_paths['data_file'])
    raw_file_path = save_paths['raw_file']
    data_file_path = save_paths['data_file']
    try:
        if source == "fish":
            fetch_user_gamedata(raw_file_path, data_file_path, username, params, source=source)
        elif source == "int_html":
            update_b50_data_int(raw_file_path, data_file_path, username, params, parser = "html")
        elif source == "int_json":
            update_b50_data_int(raw_file_path, data_file_path, username, params, parser = "json")
        else:
            raise ValueError("未知数据源！")
        st.success(f"已从用户{username}的最新数据建立存档，时间为：{save_timestamp}")
        st.session_state.data_updated_step1 = True
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"获取B50数据时发生错误: {e}")
        st.expander("错误详情").write(traceback.format_exc())
    

def check_save_available(username, save_id):
    if not save_id:
        return False
    save_paths = get_data_paths(username, save_id)
    return os.path.exists(save_paths['data_file'])

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

    st.write("b50数据预览")
    if st.button("查看当前存档的b50数据", key="edit_b50_data"):
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

                        # 加载存档时，检查存档完整性与兼容性
                        save_paths = get_data_paths(username, selected_save_id)
                        load_full_config_safe(save_paths['data_file'], username)

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

    @st.dialog("从HTML源码导入数据", width='large')
    def input_origin_data():
        st.write("请将复制的网页源代码粘贴到下方输入栏：")
        st.info("系统将会自动根据您输入的代码格式识别数据源。本窗口关闭后，请根据输入的数据类型（html或json），选择下一步对应的按钮读取数据。")
        
        root_save_dir = get_user_base_dir(username) # html或json文件保存在用户根目录（不受存档版本控制）

        if os.path.exists(os.path.join(root_save_dir, f"{username}.html")):
            st.warning(f"注意，重复导入HTML代码将会覆盖已有html文件：{username}.html")
        if os.path.exists(os.path.join(root_save_dir, f"{username}.json")):
            st.warning(f"注意，重复导入dxrating.net数据将会覆盖已有json文件：{username}.json")

        data_input = st.text_area("数据输入区", height=600)
        if st.button("确认保存"):
            file_type = "json" if data_input.startswith("[{") else "html"
            dx_int_data_file = os.path.join(root_save_dir, f"{username}.{file_type}")
            print(f"正在保存{file_type}数据到{dx_int_data_file}")
            with open(dx_int_data_file, 'w', encoding="utf-8") as f:
               f.write(data_input)
            st.success(f"{file_type.upper()}数据已保存！")
        if st.button("关闭窗口"):
            st.rerun() 

    st.write(f"新建b50存档")
    with st.container(border=True):
        # ======= Data from FISH =======
        st.info(f"从国服获取b50请使用下方按钮，您将以用户名{raw_username}从查分器获取一份新的B50数据，系统将自动为您创建一份新的存档。")

        if st.button("从水鱼获取b50数据（国服）"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # 从存档路径得到新存档的时间戳
            if save_id:
                os.makedirs(save_dir, exist_ok=True) # 新建存档文件夹
                st.session_state.save_id = save_id
                with st.spinner("正在获取数据更新..."):
                    fetch_new_achievement_data(
                        raw_username,
                        current_paths,
                        source="fish",
                        params={
                            "type": "maimai",
                            "query": "best"
                        }
                    )

        if st.button("从水鱼获取AP b50存档"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # 从存档路径得到新存档的时间戳
            if save_id:
                os.makedirs(save_dir, exist_ok=True) # 新建存档文件夹
                st.session_state.save_id = save_id
                with st.spinner("正在获取数据更新..."):
                    fetch_new_achievement_data(
                        raw_username,
                        current_paths,
                        source="fish",
                        params={
                            "type": "maimai",
                            "query": "all",
                            "filter": {
                                "tag": "ap",
                                "top": 50
                            },
                        }
                    )


        # ======= Data from DX Web =======
        st.info("如使用国际服/日服数据，请按照下列顺序操作。国服用户请忽略。")
        st.info("国际服/日服数据导入方式暂不支持AP50等特殊数据自动筛选！\n 如需制作请在‘创建自定义B50存档’页面中手动编辑存档。")

        st.markdown("1. 如果您还没有过任何外服存档，请点击下方按钮生成一份空白存档。")
        if st.button("新建空白存档", key="dx_int_create_new_save"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # 从存档路径得到新存档的时间戳
            os.makedirs(save_dir, exist_ok=True) # 新建存档文件夹
            st.session_state.save_id = save_id
            st.success(f"已新建空白存档！用户名：{username}，存档时间：{save_id}")

        st.write("如果已有存档，需要更新外服存档数据，请在上方加载本地存档后，执行下面两步：")
        
        st.markdown("2. 导入b50源代码")
        if st.button("从源代码导入b50"):
            save_id = st.session_state.get('save_id', None)
            if not save_id:
                st.error("请先新建存档，或加载已有存档！")
            else:
                input_origin_data()

        st.markdown("3. 根据导入的数据类型，选择下方按钮读取数据（二选一，重复导入将会覆盖当前存档）")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("从本地HTML读取b50"):
                with st.spinner("正在读取HTML数据..."):
                    save_id = st.session_state.get('save_id', None)
                    if not save_id:
                        st.error("请先新建存档，或加载已有存档！")
                    else:
                        current_paths = get_data_paths(username, save_id)  # 获取当前存档路径
                        fetch_new_achievement_data(
                            raw_username,
                            current_paths,
                            source="int_html",
                            params={
                                "type": "maimai",
                                "query": "best"
                            }
                        )

        with col2:
            if st.button("从本地JSON读取b50"):
                with st.spinner("正在读取JSON数据..."):
                    save_id = st.session_state.get('save_id', None)
                    if not save_id:
                        st.error("请先新建存档，或加载已有存档！")
                    else:
                        current_paths = get_data_paths(username, save_id)  # 获取当前存档路径
                        fetch_new_achievement_data(
                            raw_username,
                            current_paths,
                            source="int_json",
                            params={
                                "type": "maimai",
                                "query": "best"
                            }
                        )


    if st.session_state.get('data_updated_step1', False):
        st.write("确认你的b50数据无误后，请点击进行下一步按钮开始进行视频生成准备。")
        if st.button("进行下一步"):
            st.switch_page("st_pages/Generate_Pic_Resources.py")

    st.divider()

    with st.expander("从旧版本（v0.3.4及以下）迁移存档"):
        save_loaded = st.session_state.get('migrate_save_loaded', False)
        st.info("如果您之前使用过旧版本的b50视频生成器，可以尝试按照顺序执行以下步骤以转移存档（不保证成功率）。")
        
        st.markdown("1. 点击下方按钮生成一份空白存档。")
        if st.button("新建空白存档", key="migrate_create_new_save"):
            current_paths = get_data_paths(username, timestamp=None)  # 获取新的存档路径
            save_id = os.path.basename(os.path.dirname(current_paths['data_file']))  # 从存档路径得到新存档的时间戳
            os.makedirs(os.path.dirname(current_paths['raw_file']), exist_ok=True)
            st.session_state.save_id = save_id
            st.session_state.migrate_save_loaded = True
            st.rerun()

        st.markdown(f"2. 点击下方按钮打开存档文件夹。请前往旧版本生成器的`b50_datas`目录，找到其中所有含有当前用户名`{username}`的`.json`文件，并将它们复制到新的存档目录中。")
        if save_loaded:
            st.success(f"已加载新建空白存档！用户名：{username}，存档时间：{save_id}")

        if st.button("打开存档文件夹", key="migrate_open_save_dir", disabled=not save_loaded):
            version_dir = get_user_version_dir(username, st.session_state.save_id)
            absolute_path = os.path.abspath(version_dir)
            open_file_explorer(absolute_path)

        st.markdown("3. 复制完成后，点击下方按钮将旧版数据文件转换为新版本。")
        if st.button("转换存档数据", disabled=not save_loaded):
            current_paths = get_data_paths(username, st.session_state.save_id)
            version_dir = get_user_version_dir(username, st.session_state.save_id)
            convert_old_files(version_dir, username, current_paths)  # 转换旧版本文件名
            load_full_config_safe(current_paths['data_file'], username)  # 转换旧版本config json文件
            st.session_state.data_updated_step1 = True
        
        st.markdown("4. 点击下方按钮打开视频下载目录。请前往旧版本生成器的`videos\\downloads`目录，将已下载的视频文件复制到新的目录。如果还没有下载任何视频文件，可以跳过此步骤。")
        if st.button("打开视频下载目录"):
            open_file_explorer(os.path.abspath("./videos/downloads"))
        
        st.markdown("5. 完成上述步骤后，请回到页面上方，点击“查看和修改当前存档的b50数据”按钮，检查存档数据是否正常。**图片文件不会迁移，您仍需进入下一步重新生成图片文件**。如果您已经完成了下载视频的迁移，在图片生成后可以直接跳转第4步进行内容编辑。")
else:
    st.warning("请先确定用户名！")
