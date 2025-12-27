"""
成熟的视频搜索策略模块
提供多策略搜索、结果评分和智能匹配功能
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# 兼容Python 3.9及以下版本
try:
    from dataclasses import dataclass
except ImportError:
    def dataclass(cls):
        return cls


class GameType(Enum):
    """游戏类型枚举"""
    MAIMAI = "maimai"
    CHUNITHM = "chunithm"


class SearchStrategy(Enum):
    """搜索策略枚举"""
    EXACT = "exact"  # 精确匹配：歌曲名 + 难度 + 游戏标识
    STANDARD = "standard"  # 标准匹配：歌曲名 + 难度 + 游戏标识（简化）
    SIMPLE = "simple"  # 简单匹配：歌曲名 + 难度
    MINIMAL = "minimal"  # 最小匹配：仅歌曲名


@dataclass
class SearchResult:
    """搜索结果数据类"""
    video_id: str
    title: str
    url: str
    duration: int
    score: float = 0.0  # 匹配度评分
    matched_game: bool = False  # 是否匹配游戏类型
    matched_difficulty: bool = False  # 是否匹配难度
    matched_title: bool = False  # 是否匹配歌曲名
    strategy_used: str = ""  # 使用的搜索策略


class VideoSearchStrategy:
    """
    成熟的视频搜索策略类
    提供多策略搜索、结果评分和智能匹配
    """
    
    # 游戏标识关键词（包含各种大小写变体，匹配时会统一转换为大写进行比较）
    GAME_KEYWORDS = {
        GameType.CHUNITHM: {
            "primary": ["CHUNITHM", "chunithm", "Chunithm", "チュウニズム", "中二", "中二节奏"],
            "secondary": ["譜面確認", "譜面", "譜面動画"]
        },
        GameType.MAIMAI: {
            "primary": ["maimai", "Maimai", "MAIMAI", "舞萌", "でらっく", "デラックス"],
            "secondary": ["外部出力", "譜面確認", "譜面"]
        }
    }
    
    # 难度关键词映射（包含各种大小写变体，匹配时会统一转换为大写进行比较）
    DIFFICULTY_KEYWORDS = {
        "BASIC": ["Basic", "BASIC", "basic", "绿谱", "绿"],
        "ADVANCE": ["Advance", "ADVANCE", "advance", "ADV", "adv", "黄谱", "黄"],
        "EXPERT": ["Expert", "EXPERT", "expert", "EXP", "exp", "红谱", "红"],
        "MASTER": ["Master", "MASTER", "master", "MAS", "mas", "紫谱", "紫"],
        "RE:MASTER": ["Re:MASTER", "RE:MASTER", "re:master", "Re:Master", "REM", "rem", "白谱", "白"],
        "ULTIMA": ["ULTIMA", "ultima", "Ultima", "ULT", "ult", "黑谱", "黑"]
    }
    
    def __init__(self, game_type: str):
        self.game_type = GameType(game_type)
        self.difficulty_keywords = self.DIFFICULTY_KEYWORDS
        self.game_keywords = self.GAME_KEYWORDS[self.game_type]
    
    def _clean_title_for_search(self, title: str) -> str:
        """
        清理歌曲名，移除可能影响搜索的特殊字符
        移除 '-'、'@'、'&' 等不常规符号，YouTube搜索可能无法正确识别
        """
        # 移除首尾空白
        cleaned = title.strip()
        
        # 移除或替换可能影响搜索的字符
        # 1. 移除常见的特殊符号（替换为空格）
        special_chars = ['-', '@', '&', '#', '%', '*', '+', '=', '|', '\\', '/', '<', '>', '^', '~', '`']
        for char in special_chars:
            cleaned = cleaned.replace(char, ' ')
        
        # 2. 移除其他可能影响搜索的特殊字符
        # 保留常见的标点符号（如 . , ! ? : ; " ' ( ) [ ] { }），但移除可能造成问题的字符
        # 将多个连续空格替换为单个空格
        import re
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()
    
    def generate_search_keywords(self, title_name: str, difficulty_name: str, 
                                 chart_type: Optional[int] = None) -> List[Tuple[str, SearchStrategy]]:
        """
        生成多个搜索关键词变体，按优先级排序
        
        Returns:
            List[Tuple[str, SearchStrategy]]: (关键词, 策略) 的列表，按优先级排序
        """
        keywords = []
        # 清理歌曲名，移除特殊字符
        clean_title = self._clean_title_for_search(title_name)
        
        # 获取难度标识
        dif_name = self._get_difficulty_name(difficulty_name)
        type_name = self._get_chart_type_name(chart_type) if chart_type is not None else ""
        
        # 策略1: 精确匹配 - 歌曲名 + 难度 + 游戏标识（完整）
        if self.game_type == GameType.CHUNITHM:
            if dif_name:
                keywords.append((f"{clean_title} {dif_name} CHUNITHM 譜面確認", SearchStrategy.EXACT))
                keywords.append((f"{clean_title} {dif_name} CHUNITHM", SearchStrategy.EXACT))
        else:  # MAIMAI
            if type_name and dif_name:
                keywords.append((f"{clean_title} {type_name} {dif_name} maimai 外部出力", SearchStrategy.EXACT))
                keywords.append((f"{clean_title} {type_name} {dif_name} maimai", SearchStrategy.EXACT))
            elif dif_name:
                keywords.append((f"{clean_title} {dif_name} maimai", SearchStrategy.EXACT))
        
        # 策略2: 标准匹配 - 歌曲名 + 难度 + 游戏标识（简化）
        if dif_name:
            if self.game_type == GameType.CHUNITHM:
                keywords.append((f"{clean_title} {dif_name} CHUNITHM", SearchStrategy.STANDARD))
            else:
                if type_name:
                    keywords.append((f"{clean_title} {type_name} {dif_name} maimai", SearchStrategy.STANDARD))
                else:
                    keywords.append((f"{clean_title} {dif_name} maimai", SearchStrategy.STANDARD))
        
        # 策略3: 简单匹配 - 歌曲名 + 难度（不含游戏标识）
        if dif_name:
            keywords.append((f"{clean_title} {dif_name}", SearchStrategy.SIMPLE))
        
        # 策略4: 最小匹配 - 仅歌曲名
        keywords.append((clean_title, SearchStrategy.MINIMAL))
        
        return keywords
    
    def _get_difficulty_name(self, difficulty_name: str) -> str:
        """获取难度英文名称"""
        mapping = {
            "BASIC": "Basic",
            "ADVANCE": "Advance",
            "EXPERT": "Expert",
            "MASTER": "Master",
            "RE:MASTER": "Re:MASTER",
            "ULTIMA": "ULTIMA"
        }
        return mapping.get(difficulty_name, "")
    
    def _get_chart_type_name(self, chart_type: int) -> str:
        """获取谱面类型名称（仅舞萌）"""
        if self.game_type == GameType.MAIMAI:
            return "DX" if chart_type == 1 else "SD"
        return ""
    
    def score_result(self, video_title: str, video_id: str, 
                    target_title: str, target_difficulty: str,
                    search_strategy: SearchStrategy) -> SearchResult:
        """
        对搜索结果进行评分
        
        Args:
            video_title: 视频标题
            target_title: 目标歌曲名
            target_difficulty: 目标难度
            search_strategy: 使用的搜索策略
            
        Returns:
            SearchResult: 包含评分和匹配信息的搜索结果
        """
        title_upper = video_title.upper()
        target_title_upper = target_title.upper()
        
        # 基础评分
        score = 0.0
        
        # 1. 游戏类型匹配（最重要，40分）
        matched_game = self._check_game_match(title_upper)
        if matched_game:
            score += 40.0
        else:
            # 检查是否匹配了其他游戏类型（严重扣分）
            other_game_type = GameType.MAIMAI if self.game_type == GameType.CHUNITHM else GameType.CHUNITHM
            other_game_keywords = self.GAME_KEYWORDS[other_game_type]["primary"]
            matched_other_game = any(kw.upper() in title_upper for kw in other_game_keywords)
            
            if matched_other_game:
                # 如果匹配了其他游戏类型，大幅扣分（确保不会被选中）
                score -= 50.0
            else:
                # 如果搜索策略是简化版本，不匹配游戏类型会扣分
                if search_strategy in [SearchStrategy.SIMPLE, SearchStrategy.MINIMAL]:
                    score -= 20.0
        
        # 2. 歌曲名匹配（30分）
        matched_title = self._check_title_match(title_upper, target_title_upper)
        if matched_title:
            score += 30.0
            # 完全匹配额外加分
            if target_title_upper in title_upper:
                score += 10.0
        
        # 3. 难度匹配（20分）
        matched_difficulty = self._check_difficulty_match(title_upper, target_difficulty)
        if matched_difficulty:
            score += 20.0
        
        # 4. 谱面确认相关关键词（10分）
        if any(kw in title_upper for kw in ["譜面確認", "譜面", "譜面動画", "外部出力"]):
            score += 10.0
        
        # 5. 根据搜索策略调整分数
        strategy_bonus = {
            SearchStrategy.EXACT: 5.0,
            SearchStrategy.STANDARD: 3.0,
            SearchStrategy.SIMPLE: 0.0,
            SearchStrategy.MINIMAL: -5.0
        }
        score += strategy_bonus.get(search_strategy, 0.0)
        
        return SearchResult(
            video_id=video_id,
            title=video_title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            duration=0,  # 需要从外部设置
            score=score,
            matched_game=matched_game,
            matched_difficulty=matched_difficulty,
            matched_title=matched_title,
            strategy_used=search_strategy.value
        )
    
    def _check_game_match(self, title_upper: str) -> bool:
        """检查是否匹配游戏类型"""
        # 首先检查是否匹配了其他游戏类型（排除误判）
        other_game_type = GameType.MAIMAI if self.game_type == GameType.CHUNITHM else GameType.CHUNITHM
        other_game_keywords = self.GAME_KEYWORDS[other_game_type]["primary"]
        
        # 如果标题中包含其他游戏的关键词，说明不匹配当前游戏类型
        for keyword in other_game_keywords:
            if keyword.upper() in title_upper:
                return False
        
        # 检查主要关键词
        for keyword in self.game_keywords["primary"]:
            if keyword.upper() in title_upper:
                return True
        return False
    
    def _check_title_match(self, video_title: str, target_title: str) -> bool:
        """检查歌曲名是否匹配"""
        # 移除特殊字符和空格，进行模糊匹配
        def normalize(text: str) -> str:
            # 移除特殊字符，只保留字母数字
            text = re.sub(r'[^\w\s]', '', text)
            # 移除多余空格
            text = ' '.join(text.split())
            return text.upper()
        
        video_normalized = normalize(video_title)
        target_normalized = normalize(target_title)
        
        # 完全包含
        if target_normalized in video_normalized:
            return True
        
        # 检查主要词汇是否匹配（至少匹配50%的词汇）
        target_words = set(target_normalized.split())
        video_words = set(video_normalized.split())
        
        if len(target_words) == 0:
            return False
        
        matched_words = target_words & video_words
        match_ratio = len(matched_words) / len(target_words)
        
        return match_ratio >= 0.5
    
    def _check_difficulty_match(self, title_upper: str, difficulty: str) -> bool:
        """检查难度是否匹配"""
        if difficulty not in self.difficulty_keywords:
            return False
        
        difficulty_keywords = self.difficulty_keywords[difficulty]
        return any(kw.upper() in title_upper for kw in difficulty_keywords)
    
    def filter_and_rank_results(self, results: List[Dict], target_title: str, 
                                target_difficulty: str, search_strategy: SearchStrategy,
                                min_score: float = 20.0) -> List[SearchResult]:
        """
        过滤和排序搜索结果
        
        Args:
            results: 原始搜索结果列表
            target_title: 目标歌曲名
            target_difficulty: 目标难度
            search_strategy: 使用的搜索策略
            min_score: 最低评分阈值
            
        Returns:
            List[SearchResult]: 评分和排序后的搜索结果
        """
        scored_results = []
        
        for result in results:
            # 优先使用pure_id，如果没有则从id或url中提取
            video_id = result.get('pure_id', '')
            if not video_id:
                # 尝试从id字段提取（可能是URL）
                id_field = result.get('id', '')
                if id_field:
                    if 'watch?v=' in id_field:
                        video_id = id_field.split('watch?v=')[1].split('&')[0]
                    elif not id_field.startswith('http'):
                        video_id = id_field
            
            # 如果还是没有，从URL中提取
            if not video_id:
                url = result.get('url', '')
                if 'watch?v=' in url:
                    video_id = url.split('watch?v=')[1].split('&')[0]
                elif url and not url.startswith('http'):
                    video_id = url
            
            if not video_id:
                continue  # 跳过无法提取ID的结果
            
            video_title = result.get('title', '')
            scored_result = self.score_result(
                video_title=video_title,
                video_id=video_id,
                target_title=target_title,
                target_difficulty=target_difficulty,
                search_strategy=search_strategy
            )
            
            # 设置时长
            scored_result.duration = result.get('duration', 0)
            scored_result.url = result.get('url', scored_result.url)
            
            # 只保留评分高于阈值的结果
            if scored_result.score >= min_score:
                scored_results.append(scored_result)
        
        # 按评分降序排序
        scored_results.sort(key=lambda x: x.score, reverse=True)
        
        return scored_results
    
    def get_best_match(self, results: List[SearchResult]) -> Optional[SearchResult]:
        """
        从评分结果中选择最佳匹配
        
        优先选择：
        1. 匹配游戏类型的（必须）
        2. 匹配难度的
        3. 评分最高的
        """
        if not results:
            return None
        
        # 首先排除匹配了其他游戏类型的结果（即使评分高也要排除）
        other_game_type = GameType.MAIMAI if self.game_type == GameType.CHUNITHM else GameType.CHUNITHM
        other_game_keywords = self.GAME_KEYWORDS[other_game_type]["primary"]
        
        valid_results = []
        for r in results:
            title_upper = r.title.upper()
            # 检查是否包含其他游戏的关键词
            has_other_game = any(kw.upper() in title_upper for kw in other_game_keywords)
            if not has_other_game:
                valid_results.append(r)
        
        # 如果没有有效结果，返回 None（不返回其他游戏的结果）
        if not valid_results:
            return None
        
        # 优先选择匹配游戏类型的结果
        game_matched = [r for r in valid_results if r.matched_game]
        if game_matched:
            # 在匹配游戏类型的结果中，优先选择匹配难度的
            difficulty_matched = [r for r in game_matched if r.matched_difficulty]
            if difficulty_matched:
                return difficulty_matched[0]
            return game_matched[0]
        
        # 如果没有匹配游戏类型的，返回评分最高的有效结果
        return valid_results[0]

