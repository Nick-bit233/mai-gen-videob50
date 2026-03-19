"""
ChartUtils - Chart 数据验证和转换工具

用于 Make_Custom_Save 页面的手动覆写功能，提供：
- 字段验证
- 文本到数据库类型的转换
- 下拉选项常量
"""

from typing import Dict, List, Tuple, Optional, Any
import re


# ============================================================
# 下拉选项常量
# ============================================================

# maimai 谱面类型
MAIMAI_CHART_TYPE_OPTIONS = {
    "Standard (标准)": 0,
    "Deluxe (DX)": 1,
    "Utage (宴会场)": 2,
}

# chunithm 谱面类型
CHUNITHM_CHART_TYPE_OPTIONS = {
    "Normal (标准)": 0,
    "WORLD'S END": 1,
}

# maimai 难度
MAIMAI_LEVEL_INDEX_OPTIONS = {
    "BASIC": 0,
    "ADVANCED": 1,
    "EXPERT": 2,
    "MASTER": 3,
    "Re:MASTER": 4,
}

# chunithm 难度
CHUNITHM_LEVEL_INDEX_OPTIONS = {
    "BASIC": 0,
    "ADVANCED": 1,
    "EXPERT": 2,
    "MASTER": 3,
    "ULTIMA": 4,
    "WORLD'S END": 5,
}

# maimai FC 状态
MAIMAI_FC_STATUS_OPTIONS = ["none", "fc", "fcp", "ap", "app"]

# maimai FS 状态
MAIMAI_FS_STATUS_OPTIONS = ["none", "sync", "fs", "fsp", "fsd", "fsdp"]

# chunithm FC 状态
CHUNITHM_FC_STATUS_OPTIONS = ["none", "fc", "aj", "ajc"]

# chunithm Sync 状态（FullChain）
CHUNITHM_SYNC_STATUS_OPTIONS = ["none", "fc", "fcr"]


def get_chart_type_options(game_type: str) -> Dict[str, int]:
    """获取指定游戏类型的谱面类型选项"""
    if game_type == "maimai":
        return MAIMAI_CHART_TYPE_OPTIONS
    elif game_type == "chunithm":
        return CHUNITHM_CHART_TYPE_OPTIONS
    else:
        return {}


def get_level_index_options(game_type: str) -> Dict[str, int]:
    """获取指定游戏类型的难度选项"""
    if game_type == "maimai":
        return MAIMAI_LEVEL_INDEX_OPTIONS
    elif game_type == "chunithm":
        return CHUNITHM_LEVEL_INDEX_OPTIONS
    else:
        return {}


def get_fc_status_options(game_type: str) -> List[str]:
    """获取指定游戏类型的 FC 状态选项"""
    if game_type == "maimai":
        return MAIMAI_FC_STATUS_OPTIONS
    elif game_type == "chunithm":
        return CHUNITHM_FC_STATUS_OPTIONS
    else:
        return []


def get_fs_status_options(game_type: str) -> List[str]:
    """获取指定游戏类型的 FS/Sync 状态选项"""
    if game_type == "maimai":
        return MAIMAI_FS_STATUS_OPTIONS
    elif game_type == "chunithm":
        return CHUNITHM_SYNC_STATUS_OPTIONS
    else:
        return []


# ============================================================
# 验证和转换函数
# ============================================================

def validate_required_field(value: Any, field_name: str) -> List[str]:
    """验证必填字段"""
    errors = []
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{field_name} 不能为空")
    return errors


def try_parse_difficulty(difficulty) -> Optional[float]:
    """
    尝试将定数解析为浮点数
    
    Args:
        difficulty: 定数值，可以是 float、int 或字符串（如 "14.9", "15.0", "?", "暂无"）
    
    Returns:
        解析成功返回浮点数，失败返回 None
    """
    if difficulty is None:
        return None
    
    # 已经是数值类型
    if isinstance(difficulty, (int, float)):
        if difficulty < 0 or difficulty > 20:
            return None
        return float(difficulty)
    
    # 字符串解析
    if isinstance(difficulty, str):
        if not difficulty.strip():
            return None
        try:
            val = float(difficulty.strip())
            # 验证范围
            if val < 0 or val > 20:
                return None
            return val
        except (ValueError, TypeError):
            return None
    
    return None


def convert_and_validate_difficulty(difficulty_str: str) -> Tuple[Optional[str], List[str]]:
    """
    将定数字符串转换为数据库存储格式
    
    Args:
        difficulty_str: 用户输入的定数字符串，如 "14.9", "15.0", "?", "暂无"
    
    Returns:
        (转换后的定数字符串, 错误列表)
    
    Note:
        - 允许任意非空字符串输入
        - 图片生成时会自动判断是否为数字，非数字时使用文字渲染
        - Rating 计算时非数字定数返回 0
    """
    errors = []
    
    if not difficulty_str or not difficulty_str.strip():
        return None, ["定数不能为空"]
    
    difficulty_str = difficulty_str.strip()
    
    # 尝试解析为浮点数进行校验（但不强制要求）
    difficulty_val = try_parse_difficulty(difficulty_str)
    
    if difficulty_val is not None:
        # 是有效数字，规范化存储格式
        return str(difficulty_val), errors
    else:
        # 非数字字符串，直接存储原字符串
        # 限制长度防止过长
        if len(difficulty_str) > 20:
            errors.append(f"定数字符串过长: {len(difficulty_str)} 字符（最大 20 字符）")
            return None, errors
        return difficulty_str, errors


def convert_and_validate_achievement(achievement_str: str, game_type: str) -> Tuple[Optional[float], List[str]]:
    """
    将达成率/分数字符串转换为数据库存储格式
    
    Args:
        achievement_str: 用户输入的达成率/分数
        game_type: 游戏类型 ("maimai" 或 "chunithm")
    
    Returns:
        (转换后的数值, 错误列表)
    
    Note:
        - maimai: 达成率范围 0.0000 - 101.0000 (百分比，如 100.6225)
        - chunithm: 分数范围 0 - 1010000 (整数分数)
    """
    errors = []
    
    if not achievement_str or not achievement_str.strip():
        return 0.0, []  # 默认值为 0
    
    achievement_str = achievement_str.strip()
    
    try:
        achievement_val = float(achievement_str)
        
        if game_type == "maimai":
            if achievement_val < 0 or achievement_val > 101.0:
                errors.append(f"maimai 达成率范围应为 0-101: {achievement_val}")
                return None, errors
            return achievement_val, errors
            
        elif game_type == "chunithm":
            if achievement_val < 0 or achievement_val > 1010000:
                errors.append(f"chunithm 分数范围应为 0-1010000: {achievement_val}")
                return None, errors
            # chunithm 分数存储为整数
            return int(achievement_val), errors
            
        else:
            return achievement_val, errors
            
    except ValueError:
        errors.append(f"达成率/分数格式错误: '{achievement_str}' 不是有效的数字")
        return None, errors


def convert_and_validate_dx_score(dx_score_str: str) -> Tuple[Optional[int], List[str]]:
    """
    将 DX 分数字符串转换为整数
    
    Args:
        dx_score_str: 用户输入的 DX 分数
    
    Returns:
        (转换后的整数, 错误列表)
    """
    errors = []
    
    if not dx_score_str or not dx_score_str.strip():
        return 0, []  # 默认值为 0
    
    dx_score_str = dx_score_str.strip()
    
    try:
        dx_score_val = int(float(dx_score_str))  # 先转 float 再转 int，兼容用户输入小数
        
        if dx_score_val < 0:
            errors.append(f"DX 分数不能为负数: {dx_score_val}")
            return None, errors
        
        return dx_score_val, errors
        
    except ValueError:
        errors.append(f"DX 分数格式错误: '{dx_score_str}' 不是有效的整数")
        return None, errors


def convert_and_validate_max_dx_score(max_dx_score_str: str) -> Tuple[Optional[int], List[str]]:
    """
    将最大 DX 分数字符串转换为整数
    
    Args:
        max_dx_score_str: 用户输入的最大 DX 分数
    
    Returns:
        (转换后的整数, 错误列表)
    """
    return convert_and_validate_dx_score(max_dx_score_str)  # 逻辑相同


def convert_and_validate_play_count(play_count_str: str) -> Tuple[Optional[int], List[str]]:
    """
    将游玩次数字符串转换为整数
    
    Args:
        play_count_str: 用户输入的游玩次数
    
    Returns:
        (转换后的整数, 错误列表)
    """
    errors = []
    
    if not play_count_str or not play_count_str.strip():
        return 0, []  # 默认值为 0
    
    play_count_str = play_count_str.strip()
    
    try:
        play_count_val = int(float(play_count_str))
        
        if play_count_val < 0:
            errors.append(f"游玩次数不能为负数: {play_count_val}")
            return None, errors
        
        return play_count_val, errors
        
    except ValueError:
        errors.append(f"游玩次数格式错误: '{play_count_str}' 不是有效的整数")
        return None, errors


def convert_and_validate_rating(rating_str: str, game_type: str) -> Tuple[Optional[float], List[str]]:
    """
    将 Rating 字符串转换为数据库存储格式
    
    Args:
        rating_str: 用户输入的 Rating
        game_type: 游戏类型 ("maimai" 或 "chunithm")
    
    Returns:
        (转换后的数值, 错误列表)
    
    Note:
        - maimai: dx_rating 为整数
        - chunithm: chuni_rating 为浮点数
    """
    errors = []
    
    if not rating_str or not rating_str.strip():
        return 0, []  # 默认值为 0
    
    rating_str = rating_str.strip()
    
    try:
        rating_val = float(rating_str)
        
        if rating_val < 0:
            errors.append(f"Rating 不能为负数: {rating_val}")
            return None, errors
        
        if game_type == "maimai":
            # maimai 存储为整数
            return int(rating_val), errors
        else:
            # chunithm 存储为浮点数
            return rating_val, errors
            
    except ValueError:
        errors.append(f"Rating 格式错误: '{rating_str}' 不是有效的数字")
        return None, errors


def validate_fc_status(fc_status: str, game_type: str) -> Tuple[bool, List[str]]:
    """
    验证 FC 状态是否合法
    
    Args:
        fc_status: FC 状态字符串
        game_type: 游戏类型
    
    Returns:
        (是否有效, 错误列表)
    """
    errors = []
    valid_options = get_fc_status_options(game_type)
    
    if fc_status not in valid_options:
        errors.append(f"无效的 FC 状态: '{fc_status}'，有效选项: {valid_options}")
        return False, errors
    
    return True, errors


def validate_fs_status(fs_status: str, game_type: str) -> Tuple[bool, List[str]]:
    """
    验证 FS/Sync 状态是否合法
    
    Args:
        fs_status: FS/Sync 状态字符串
        game_type: 游戏类型
    
    Returns:
        (是否有效, 错误列表)
    """
    errors = []
    valid_options = get_fs_status_options(game_type)
    
    if fs_status not in valid_options:
        errors.append(f"无效的 FS/Sync 状态: '{fs_status}'，有效选项: {valid_options}")
        return False, errors
    
    return True, errors


# ============================================================
# 表单数据转换（主函数）
# ============================================================

def validate_and_convert_chart_data(form_data: Dict, game_type: str) -> Tuple[Optional[Dict], List[str]]:
    """
    验证并转换用户输入的 chart 数据
    
    Args:
        form_data: 表单数据字典
        game_type: 游戏类型 ("maimai" 或 "chunithm")
    
    Returns:
        (转换后的 chart_data 字典, 错误列表)
    """
    errors = []
    chart_data = {'game_type': game_type}
    
    # 必填字段验证
    song_name = form_data.get('song_name', '').strip()
    errors.extend(validate_required_field(song_name, "曲名"))
    chart_data['song_name'] = song_name
    
    artist = form_data.get('artist', '').strip()
    errors.extend(validate_required_field(artist, "曲师"))
    chart_data['artist'] = artist
    
    song_id = form_data.get('song_id', '').strip()
    errors.extend(validate_required_field(song_id, "歌曲ID"))
    chart_data['song_id'] = song_id
    
    # 谱面类型转换（下拉选择，值已经是整数）
    chart_type = form_data.get('chart_type', 0)
    try:
        chart_data['chart_type'] = int(chart_type)
    except (ValueError, TypeError):
        errors.append(f"谱面类型格式错误: {chart_type}")
        chart_data['chart_type'] = 0
    
    # 难度转换（下拉选择，值已经是整数）
    level_index = form_data.get('level_index', 3)  # 默认 MASTER
    try:
        chart_data['level_index'] = int(level_index)
    except (ValueError, TypeError):
        errors.append(f"难度格式错误: {level_index}")
        chart_data['level_index'] = 3
    
    # 定数转换
    difficulty_str = form_data.get('difficulty', '0')
    difficulty, diff_errors = convert_and_validate_difficulty(difficulty_str)
    errors.extend(diff_errors)
    if difficulty is not None:
        chart_data['difficulty'] = difficulty
    
    # max_dx_score（仅 maimai）
    if game_type == 'maimai':
        max_dx_score_str = form_data.get('max_dx_score', '0')
        max_dx_score, max_errors = convert_and_validate_max_dx_score(max_dx_score_str)
        errors.extend(max_errors)
        if max_dx_score is not None:
            chart_data['max_dx_score'] = max_dx_score
    
    # 如果有错误，返回 None
    if errors:
        return None, errors
    
    return chart_data, errors


def validate_and_convert_record_data(form_data: Dict, game_type: str, auto_calc_rating: bool = True) -> Tuple[Optional[Dict], List[str]]:
    """
    验证并转换用户输入的 record 数据
    
    Args:
        form_data: 表单数据字典
        game_type: 游戏类型
        auto_calc_rating: 是否自动计算 Rating
    
    Returns:
        (转换后的 record_data 字典, 错误列表)
    """
    errors = []
    record_data = {}
    
    # clip_title_name
    clip_title_name = form_data.get('clip_title_name', '').strip()
    if clip_title_name:
        record_data['clip_title_name'] = clip_title_name
    else:
        record_data['clip_title_name'] = "Clip"  # 默认值
    
    # 达成率/分数
    achievement_str = form_data.get('achievement', '0')
    achievement, ach_errors = convert_and_validate_achievement(achievement_str, game_type)
    errors.extend(ach_errors)
    if achievement is not None:
        record_data['achievement'] = achievement
    
    # FC 状态
    fc_status = form_data.get('fc_status', 'none')
    is_valid_fc, fc_errors = validate_fc_status(fc_status, game_type)
    errors.extend(fc_errors)
    if is_valid_fc:
        record_data['fc_status'] = fc_status
    
    # FS/Sync 状态
    fs_status = form_data.get('fs_status', 'none')
    is_valid_fs, fs_errors = validate_fs_status(fs_status, game_type)
    errors.extend(fs_errors)
    if is_valid_fs:
        record_data['fs_status'] = fs_status
    
    # 游玩次数
    play_count_str = form_data.get('play_count', '0')
    play_count, pc_errors = convert_and_validate_play_count(play_count_str)
    errors.extend(pc_errors)
    if play_count is not None:
        record_data['play_count'] = play_count
    
    # maimai 特有字段
    if game_type == 'maimai':
        # DX 分数
        dx_score_str = form_data.get('dx_score', '0')
        dx_score, dx_errors = convert_and_validate_dx_score(dx_score_str)
        errors.extend(dx_errors)
        if dx_score is not None:
            record_data['dx_score'] = dx_score
        
        # Rating
        if auto_calc_rating:
            record_data['dx_rating'] = 0  # 稍后自动计算
        else:
            rating_str = form_data.get('dx_rating', '0')
            rating, rating_errors = convert_and_validate_rating(rating_str, game_type)
            errors.extend(rating_errors)
            if rating is not None:
                record_data['dx_rating'] = rating
    
    # chunithm 特有字段
    if game_type == 'chunithm':
        if auto_calc_rating:
            record_data['chuni_rating'] = 0.0  # 稍后自动计算
        else:
            rating_str = form_data.get('chuni_rating', '0')
            rating, rating_errors = convert_and_validate_rating(rating_str, game_type)
            errors.extend(rating_errors)
            if rating is not None:
                record_data['chuni_rating'] = rating
    
    # 如果有错误，返回 None
    if errors:
        return None, errors
    
    return record_data, errors


def validate_complete_record_form(form_data: Dict, game_type: str, auto_calc_rating: bool = True) -> Tuple[Optional[Dict], List[str]]:
    """
    验证完整的记录表单（包含 chart 和 record 数据）
    
    Args:
        form_data: 表单数据字典
        game_type: 游戏类型
        auto_calc_rating: 是否自动计算 Rating
    
    Returns:
        (转换后的完整数据字典，包含 chart_data 和 record_data, 错误列表)
    """
    errors = []
    
    # 验证 chart 数据
    chart_data, chart_errors = validate_and_convert_chart_data(form_data, game_type)
    errors.extend(chart_errors)
    
    # 验证 record 数据
    record_data, record_errors = validate_and_convert_record_data(form_data, game_type, auto_calc_rating)
    errors.extend(record_errors)
    
    if errors:
        return None, errors
    
    # 合并数据
    complete_data = {
        'chart_data': chart_data,
        **record_data  # record 字段展开到顶层
    }
    
    return complete_data, errors
