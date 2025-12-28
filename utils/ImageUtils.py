import json
import os.path
import traceback

from utils.PageUtils import load_music_metadata
from PIL import Image, ImageDraw, ImageFont

# 重构note：成绩图生成模块不再主动获取外部资源（如下载封面、获取谱面详细信息等），而是依赖传入数据
# 以此减少模块间耦合，简化调用流程，由调用方负责准备所需数据

class MaiImageGenerater:
    def __init__(self, style_config=None):
        self.asset_paths = style_config.get("asset_paths", {})
        self.image_root_path = self.asset_paths.get("score_image_assets_path", "./static/assets/images/")
        self.font_path = self.asset_paths.get("ui_font", "static/assets/fonts/FOT_NewRodin_Pro_EB.otf")


    def DsLoader(self, level: int = 0, Ds: float = 0.0):
        if Ds >= 20 or Ds < 1:
            raise Exception("定数无效")

        __ds = str(Ds)

        # 根据小数点拆分字符串
        if '.' in __ds:
            IntegerPart, DecimalPart = __ds.split('.')
        else:
            IntegerPart, DecimalPart = __ds, '0'
        Background = Image.new('RGBA', (180, 120), (0, 0, 0, 0))
        Background.convert("RGBA")

        # 加载数字
        if len(IntegerPart) == 1:
            with Image.open(f'{self.image_root_path}/Numbers/{str(level)}/{IntegerPart}.png') as Number:
                Background.paste(Number, (48, 60), Number)
        else:
            with Image.open(f'{self.image_root_path}/Numbers/{str(level)}/1.png') as FirstNumber:
                Background.paste(FirstNumber, (18, 60), FirstNumber)
            with Image.open(f'{self.image_root_path}/Numbers/{str(level)}/{IntegerPart[1]}.png') as SecondNumber:
                Background.paste(SecondNumber, (48, 60), SecondNumber)
        if len(DecimalPart) == 1:
            with Image.open(f'{self.image_root_path}/Numbers/{str(level)}/{DecimalPart}.png') as Number:
                Number = Number.resize((32, 40), Image.LANCZOS)
                Background.paste(Number, (100, 79), Number)
        else:
            raise Exception("定数无效")

        # 加载加号
        if int(DecimalPart) >= 6:
            with Image.open(f"{self.image_root_path}/Numbers/{str(level)}/plus.png") as PlusMark:
                Background.paste(PlusMark, (75, 50), PlusMark)

        return Background

    def TypeLoader(self, Type: int = 0):
        _type = Type  # 0 for SD, 1 for DX
        with Image.open(f"{self.image_root_path}/Types/{_type}.png") as _Type:
            _Type = _Type.resize((180, 50), Image.BICUBIC)
            return _Type.copy()

    def AchievementLoader(self, Achievement: str):
        IntegerPart = Achievement.split('.')[0]
        DecimalPart = Achievement.split('.')[1]

        Background = Image.new('RGBA', (800, 118), (0, 0, 0, 0))
        Background.convert("RGBA")

        for __index, __digit in enumerate(IntegerPart):
            with Image.open(f"{self.image_root_path}/Numbers/AchievementNumber/{__digit}.png") as Number:
                Background.paste(Number, (__index * 78 + (3 - len(IntegerPart)) * 78, 0), Number)

        for __index, __digit in enumerate(DecimalPart):
            with Image.open(f"{self.image_root_path}/Numbers/AchievementNumber/{__digit}.png") as Number:
                ScalLevel = 0.75
                Number = Number.resize((int(86 * ScalLevel), int(118 * ScalLevel)), Image.LANCZOS)
                Background.paste(Number, (270 + __index * int(86 * ScalLevel - 5), int(118 * (1 - ScalLevel) - 3)),
                                 Number)

        return Background

    def StarLoader(self, Star: int = 0):
        match Star:
            case _ if Star == 0:
                with Image.open(f"{self.image_root_path}/Stars/0.png") as _star:
                    return _star.copy()
            case _ if Star == 1 or Star == 2:
                with Image.open(f"{self.image_root_path}/Stars/1.png") as _star:
                    return _star.copy()
            case _ if Star == 3 or Star == 4:
                with Image.open(f"{self.image_root_path}/Stars/3.png") as _star:
                    return _star.copy()
            case _ if Star == 5:
                with Image.open(f"{self.image_root_path}/Stars/5.png") as _star:
                    return _star.copy()
            case _:
                with Image.open(f"{self.image_root_path}/Stars/0.png") as _star:
                    return _star.copy()

    def ComboStatusLoader(self, ComboStatus: int = 0):
        match ComboStatus:
            case _ if ComboStatus == 'fc':
                with Image.open(f"{self.image_root_path}/ComboStatus/1.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if ComboStatus == 'fcp':
                with Image.open(f"{self.image_root_path}/ComboStatus/2.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if ComboStatus == 'ap':
                with Image.open(f"{self.image_root_path}/ComboStatus/3.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if ComboStatus == 'app':
                with Image.open(f"{self.image_root_path}/ComboStatus/4.png") as _comboStatus:
                    return _comboStatus.copy()
            case _:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))

    def SyncStatusLoader(self, SyncStatus: int = 0):
        match SyncStatus:
            case _ if SyncStatus == 'fs':
                with Image.open(f"{self.image_root_path}/SyncStatus/1.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'fsp':
                with Image.open(f"{self.image_root_path}/SyncStatus/2.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'fsd':
                with Image.open(f"{self.image_root_path}/SyncStatus/3.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'fsdp':
                with Image.open(f"{self.image_root_path}/SyncStatus/4.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'sync':
                with Image.open(f"{self.image_root_path}/SyncStatus/5.png") as _syncStatus:
                    return _syncStatus.copy()
            case _:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))

    def TextDraw(self, Image, Text: str = "", Position: tuple = (0, 0)):
        # 文本居中绘制

        # 载入文字元素
        Draw = ImageDraw.Draw(Image)
        FontPath = self.font_path
        FontSize = 32
        FontColor = (255, 255, 255)
        Font = ImageFont.truetype(FontPath, FontSize)

        # 获取文本的边界框
        Bbox = Draw.textbbox((0, 0), Text, font=Font)
        # 计算文本宽度和高度
        TextWidth = Bbox[2] - Bbox[0]  # 右下角x - 左上角x
        TextHeight = Bbox[3] - Bbox[1]  # 右下角y - 左上角y
        # 计算文本左上角位置，使文本在中心点居中
        TextPosition = (Position[0] - TextWidth // 2, Position[1] - TextHeight // 2)
        # 绘制
        Draw.text(TextPosition, Text, fill=FontColor, font=Font)
        return Image

    def count_dx_stars(self, user_dx_score, max_dx_score):
        dx_stars = 0
        match user_dx_score:
            case _ if 0 <= user_dx_score < max_dx_score * 0.85:
                dx_stars = 0
            case _ if max_dx_score * 0.85 <= user_dx_score < max_dx_score * 0.9:
                dx_stars = 1
            case _ if max_dx_score * 0.9 <= user_dx_score < max_dx_score * 0.93:
                dx_stars = 2
            case _ if max_dx_score * 0.93 <= user_dx_score < max_dx_score * 0.95:
                dx_stars = 3
            case _ if max_dx_score * 0.95 <= user_dx_score < max_dx_score * 0.97:
                dx_stars = 4
            case _ if max_dx_score * 0.97 <= user_dx_score <= max_dx_score:
                dx_stars = 5
        return dx_stars

    def GenerateOneAchievement(self, record_detail: dict):
        """生成单个MaimaiDX成绩记录。

        Args:
            record_detail (dict): 成绩记录详情，包含以下字段：
                - title (str): 乐曲标题
                - ds (float): 定数
                - level_index (int): 难度颜色
                - song_id (str): 乐曲ID
                - type (str): 谱面类型
                - achievements (**str**): 达成率
                - dxScore (int): DX分数
                - fc (str): FC状态，可选值：空字符串、'fc'、'fcp'、'ap'、'app'
                - sync (str): SYNC状态，可选值：空字符串、'fs'、'fsd'、'fsdp'
                - ra (int): Rating分数

        Returns:
            Background (Image.Image): 处理后的成绩记录图片
        """
        # Initialize Background as None outside the try block
        Background = None
        
        try:
            assert record_detail['level_index'] in range(0, 5)
            image_asset_path = os.path.join(os.getcwd(),
                                            f"{self.image_root_path}/AchievementBase/{record_detail['level_index']}.png")
            dx_stars = self.count_dx_stars(record_detail['dxScore'], record_detail.get('max_dx_score', 0))
            with Image.open(image_asset_path) as Background:
                Background = Background.convert("RGBA")

                # 载入图片元素
                TempImage = Image.new('RGBA', Background.size, (0, 0, 0, 0))

                # 加载乐曲封面
                JacketPosition = (44, 53)
                Jacket = record_detail.get('jacket', None)
                if Jacket is None or not isinstance(Jacket, Image.Image):  # 如果未输入有效图片数据，则使用默认封面
                    Jacket = Image.open(f"{self.image_root_path}/Jackets/UI_Jacket_000000.png")
                TempImage.paste(Jacket, JacketPosition, Jacket)

                # 加载类型
                TypePosition = (1200, 75)
                _Type = self.TypeLoader(record_detail["type"])
                TempImage.paste(_Type, TypePosition, _Type)

                # 加载定数
                DsPosition = (1405, -55)
                Ds = self.DsLoader(record_detail["level_index"], record_detail["ds"])
                Ds = Ds.resize((270, 180), Image.LANCZOS)
                TempImage.paste(Ds, DsPosition, Ds)

                # 加载成绩
                AchievementPosition = (770, 245)
                Achievement = self.AchievementLoader(record_detail["achievements"])
                TempImage.paste(Achievement, AchievementPosition, Achievement)

                # 加载星级
                StarPosition = (820, 439)
                Star = self.StarLoader(dx_stars)
                Star = Star.resize((45, 45), Image.LANCZOS)
                TempImage.paste(Star, StarPosition, Star)

                # 加载Combo状态
                ComboStatusPosition = (960, 425)
                ComboStatus = self.ComboStatusLoader(record_detail["fc"])
                ComboStatus = ComboStatus.resize((70, 70), Image.LANCZOS)
                TempImage.paste(ComboStatus, ComboStatusPosition, ComboStatus)

                # 加载Sync状态
                SyncStatusPosition = (1040, 425)
                SyncStatus = self.SyncStatusLoader(record_detail["fs"])
                SyncStatus = SyncStatus.resize((70, 70), Image.LANCZOS)
                TempImage.paste(SyncStatus, SyncStatusPosition, SyncStatus)

                # 标题
                TextCentralPosition = (1042, 159)
                Title = record_detail['title']
                TempImage = self.TextDraw(TempImage, Title, TextCentralPosition)

                # Rating值
                TextCentralPosition = (670, 458)
                RatingText = str(record_detail['ra'])
                TempImage = self.TextDraw(TempImage, RatingText, TextCentralPosition)

                # DX星数
                TextCentralPosition = (880, 458)
                StarText = str(dx_stars)
                TempImage = self.TextDraw(TempImage, StarText, TextCentralPosition)

                # 游玩次数（暂无获取方式，b50data中若有手动填写即可显示）
                if "play_count" in record_detail:
                    PlayCount = int(record_detail["play_count"])
                else:
                    PlayCount = 0
                if PlayCount >= 1:
                    with Image.open(f"{self.image_root_path}/Playcount/PlayCountBase.png") as PlayCountBase:
                        TempImage.paste(PlayCountBase, (1170, 420), PlayCountBase)
                    TextCentralPosition = (1435, 458)
                    PlayCountText = str(PlayCount)
                    TempImage = self.TextDraw(TempImage, PlayCountText, TextCentralPosition)

                Background = Image.alpha_composite(Background, TempImage)

        except Exception as e:
            print(f"Error generating achievement: {e}")
            print(traceback.format_exc())
            Background = Image.new('RGBA', (1520, 500), (0, 0, 0, 255))

        return Background


class ChuniImageGenerater:
    def __init__(self, style_config=None):
        self.asset_paths = style_config.get("asset_paths", {})
        self.image_root_path = self.asset_paths.get("score_image_assets_path", "./static/assets/images/Chunithm")
        self.ui_font_path = self.asset_paths.get("ui_font", "./static/assets/fonts/SOURCEHANSANSSC-BOLD.OTF")
        self.title_font_path = "./static/assets/fonts/SweiBellLegCJKsc-Black.ttf"
        self.level_font_path = "./static/assets/fonts/NimbusSanL-Bol.otf"

    def FrameLoader(self, level_index: int = 0):
        with Image.open(f"{self.image_root_path}/Frames/{level_index}.png") as _frame:
            return _frame.copy()

    def LevelLoader(self, ds_cur: float, ds_next: float = 0.0):
        # TODO: FLAG依据判断以哪个版本的定数为准
        ds = ds_cur if ds_cur > 1 else ds_next
        # 根据小数点拆分字符串
        __ds = str(ds)
        if '.' in __ds:
            level, decimal = __ds.split('.')
        else:
            level, decimal = __ds, '0'
        level_number_img = Image.new('RGBA', (108, 88), (0, 0, 0, 0))

        # 绘制数字
        level_number_img = self.TextDraw(level_number_img, level, (54, 46), 
                                         font_path=self.level_font_path,
                                         font_size=60, font_color=(255, 255, 255), h_align="center")

        if int(decimal) >= 6:
            # 绘制加号
            level_number_img = self.TextDraw(level_number_img, '+', (92, 8), 
                                             font_path=self.level_font_path,
                                             font_size=42, font_color=(255, 255, 255), h_align="center")

        return level_number_img
        
    def ScoreLoader(self, score: int = 0):
        if score < 0 or score > 1010000:
            raise ValueError("分数无效")
        
        score_str_formatted = f"{score:,}"   
        score_number_img = Image.new('RGBA', (420, 100), (0, 0, 0, 0))

        # 计算总宽度以实现右对齐
        total_width = 0
        digit_size = (50, 80)  # 每个数字的宽度和高度
        comma_size = (50, 72)  # 逗号的宽度和高度
        for char in score_str_formatted:
            if char == ',':
                total_width += comma_size[0]  // 2 # 逗号宽度视为数字宽度的一半，以实现更紧凑的排列
            else:
                total_width += digit_size[0]
        
        # 从右侧开始绘制
        current_x = 420 - total_width
        
        for char in score_str_formatted:
            if char == ',':
                image_path = f"{self.image_root_path}/Numbers/AchievementNumber/comma.png"
                char_width = comma_size[0] // 2
            else:
                image_path = f"{self.image_root_path}/Numbers/AchievementNumber/{char}.png"
                char_width = digit_size[0]
            
            with Image.open(image_path) as char_img:
                # 将图片缩放到指定大小
                if char == ',':
                    char_img = char_img.resize(comma_size, Image.LANCZOS)
                else:
                    char_img = char_img.resize(digit_size, Image.LANCZOS)
                
                char_y = 28 if char == ',' else 8  # 逗号的垂直方向在数字的下方
                score_number_img.paste(char_img, (current_x, char_y), char_img)
                current_x += char_width
                
        return score_number_img
    
    def RatingLoader(self, rating: float):
        if rating < 0:
            raise ValueError("Rating值无效")
        
        # 按照rating数值选择数字图片的样式
        match rating:
            case _ if rating >= 17:
                digit_style = "ex_rainbow"
            case _ if rating >= 16:
                digit_style = "rainbow"
            case _ if rating < 16:
                digit_style = "gold"
        
        ra_number_formatted = f"{rating:.2f}"
        ra_number_img = Image.new('RGBA', (160, 50), (0, 0, 0, 0))

        # 计算总宽度实现居中对齐
        total_width = 0
        digit_size = (35, 48)
        dot_size = (33, 45)

        for char in ra_number_formatted:
            if char == '.':
                total_width += dot_size[0] // 2
            else:
                total_width += digit_size[0]
        
        current_x = (160 - total_width) // 2
        for char in ra_number_formatted:
            if char == '.':
                image_path = f"{self.image_root_path}/Numbers/RatingNumber/{digit_style}/dot.png"
                char_width = dot_size[0] // 2
                char_y = 8  # 小数点位置靠下
            else:   
                image_path = f"{self.image_root_path}/Numbers/RatingNumber/{digit_style}/{char}.png"
                char_width = digit_size[0]
                char_y = 0
            with Image.open(image_path) as char_img:
                if char == '.':
                    char_img = char_img.resize(dot_size, Image.LANCZOS)
                else:
                    char_img = char_img.resize(digit_size, Image.LANCZOS)
                ra_number_img.paste(char_img, (current_x, char_y), char_img)
                current_x += char_width

        return ra_number_img

    def ComboStatusLoader(self, combo_status: str = ""):
        match combo_status:
            case _ if combo_status == 'fc':
                with Image.open(f"{self.image_root_path}/ComboStatus/11.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if combo_status == 'aj':
                with Image.open(f"{self.image_root_path}/ComboStatus/12.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if combo_status == 'ajc':
                with Image.open(f"{self.image_root_path}/ComboStatus/13.png") as _comboStatus:
                    return _comboStatus.copy()
            case _:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))
                
    def ChainStatusLoader(self, chain_status: str = ""):
        match chain_status:
            case _ if chain_status == 'fc':  # 金full chain
                with Image.open(f"{self.image_root_path}/ComboStatus/21.png") as _chainStatus:
                    return _chainStatus.copy()
            case _ if chain_status == 'fcr': # 铂金full chain
                with Image.open(f"{self.image_root_path}/ComboStatus/22.png") as _chainStatus:
                    return _chainStatus.copy()
            case _:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))
        
    def TextDraw(self, image, text: str = "", pos: tuple = (0, 0), max_width: int = 2000,
                 font_path=None, font_size=32, font_color=(255, 255, 255), h_align: str = "center") -> Image.Image:
        """
        绘制文本，若超出最大宽度则缩小字体直至适配

        Args:
            image (PIL.Image): 目标图像
            text (str): 要绘制的文本
            pos (tuple): 基准位置 (x, y)。水平含义由 h_align 决定:
                         h_align = 'left'  -> pos 作为文本左边界
                         h_align = 'center'-> pos 作为文本水平中心
                         h_align = 'right' -> pos 作为文本右边界
                         垂直方向始终居中
            max_width (int): 最大允许宽度
            font_path (str): 字体文件路径
            font_size (int): 初始字体大小
            font_color (tuple): 字体颜色 (R, G, B)
            h_align (str): 水平对齐方式: 'left' | 'center' | 'right'
        """

        # 载入文字元素
        Draw = ImageDraw.Draw(image)
        if not font_path:
            font_path = self.ui_font_path

        # 校验对齐
        if h_align not in ("left", "center", "right"):
            raise ValueError(f"h_align 必须为 'left' | 'center' | 'right', 当前: {h_align}")

        # 动态调整字体大小以适配最大宽度
        Font = ImageFont.truetype(font_path, font_size)
        Bbox = Draw.textbbox((0, 0), text, font=Font)
        text_width = Bbox[2] - Bbox[0]

        while text_width > max_width and font_size > 10:
            font_size -= 1
            Font = ImageFont.truetype(font_path, font_size)
            Bbox = Draw.textbbox((0, 0), text, font=Font)
            text_width = Bbox[2] - Bbox[0]
        text_height = Bbox[3] - Bbox[1]
        # 计算水平起点
        if h_align == "left":
            x = pos[0]
        elif h_align == "center":
            x = pos[0] - text_width // 2
        else:  # right
            x = pos[0] - text_width
        # 垂直始终居中
        y = pos[1] - text_height // 2
        text_pos = (x, y)
        Draw.text(text_pos, text, fill=font_color, font=Font)
        return image
    
    
    def GenerateOneAchievement(self, record_detail: dict):
        """
        生成单个Chunithm成绩记录。

        Args:
            record_detail (dict): 成绩记录详情，包含以下字段：
                - title (str): 乐曲标题
                - artist (str): 艺术家
                - ds_cur (float): 定数（当前版本）
                - ds_next (float): 定数（下版本，可留空）
                - level_index (int): 难度颜色
                - score (int): 分数
                - combo_type (str): FC状态，可选值：空字符串、'fc'、'aj'、'ajc'
                - chain_type (str): 连锁状态，可选值：空字符串、'fc'、'fcr'
                - ra (float): Rating值

        Returns:
            Background (Image.Image): 处理后的成绩记录图片
        """
        def modified_ds_next(ds_cur: float, ds_next: float) -> str:
            if not ds_cur or ds_cur <= 0.0: 
                return str(ds_next)
            elif ds_next > ds_cur:
                return str(ds_next) + "↑" 
            elif ds_next < ds_cur:
                return str(ds_next) + "↓"
            else:
                return str(ds_next) + "→"

        # Initialize Background as None outside the try block
        background = None
        
        try:
            assert record_detail['level_index'] in range(0, 5)
            image_base_path = os.path.join(os.getcwd(),
                                            f"{self.image_root_path}/content_base_chunithm_verse.png")
            with Image.open(image_base_path) as background:

                # background size: 1920x1080
                background = background.convert("RGBA")
                assert background.size == (1920, 1080)

                # 载入图片元素
                _temp_img = Image.new('RGBA', background.size, (0, 0, 0, 0))

                # 加载边框
                frame = self.FrameLoader(record_detail["level_index"])
                _temp_img.paste(frame, (65, 32), frame)

                # 加载等级
                level_pos = (102, 884)
                level = self.LevelLoader(record_detail["ds_cur"], record_detail["ds_next"])
                _temp_img.paste(level, level_pos, level)

                # 加载定数（当前版本和下一版本）
                ds_cur_pos = (1562, 1018)
                ds_next_pos = (1756, 1018)
                ds_cur = record_detail["ds_cur"]
                ds_next = record_detail["ds_next"]
                ds_cur_text = str(ds_cur)
                if not ds_cur or ds_cur <= 0.0:  # 不在当前版本的谱面，使用0来标记无定数
                    ds_cur_text = "--"
                if not ds_next or ds_next <= 0.0:  # 未有新版本数据的谱面，使用0来标记无定数
                    ds_next_text = "--"
                else:
                    ds_next_text = modified_ds_next(ds_cur, ds_next)
                _temp_img = self.TextDraw(_temp_img, ds_cur_text , ds_cur_pos,
                                          font_path=self.title_font_path, 
                                          font_size=45, font_color=(77, 77, 77), h_align="center")
                _temp_img = self.TextDraw(_temp_img, ds_next_text , ds_next_pos,
                                          font_path=self.title_font_path, 
                                          font_size=45, font_color=(77, 77, 77), h_align="center")

                # 加载分数
                score_pos = (706, 958)
                score = self.ScoreLoader(record_detail["score"])
                _temp_img.paste(score, score_pos, score)
                
                # 加载Rating值
                rating_pos = (1216, 980)
                rating = self.RatingLoader(record_detail['ra'])
                _temp_img.paste(rating, rating_pos, rating)

                # 加载Combo状态
                combo_status_pos = (426, 975)
                combo_status = self.ComboStatusLoader(record_detail["combo_type"])
                combo_status = combo_status.resize((236, 38), Image.LANCZOS)
                _temp_img.paste(combo_status, combo_status_pos, combo_status)

                # 加载Chain状态
                chain_status_pos = (426, 1020)
                chain_status = self.ChainStatusLoader(record_detail["chain_type"])
                chain_status = chain_status.resize((236, 38), Image.LANCZOS)
                _temp_img.paste(chain_status, chain_status_pos, chain_status)

                # 标题
                text_title_pos = (234, 876)
                title = record_detail['title']
                _temp_img = self.TextDraw(_temp_img, title, text_title_pos, max_width=900,
                                          font_path=self.title_font_path, 
                                          font_size=48, font_color=(26, 0, 84), h_align="left")
                # 艺术家
                text_artist_pos = (234, 936)
                artist = record_detail['artist']
                _temp_img = self.TextDraw(_temp_img, artist, text_artist_pos, max_width=420,
                                          font_path=self.title_font_path, 
                                          font_size=36, font_color=(26, 0, 84), h_align="left")
                
                # 游玩次数（暂无获取方式，b50data中若有手动填写即可显示）
                if "play_count" in record_detail:
                    play_count = int(record_detail["play_count"])
                else:
                    play_count = 0
                if play_count >= 1:
                    with Image.open(f"{self.image_root_path}/Playcount/PlayCountBase.png") as PlayCountBase:
                        _temp_img.paste(PlayCountBase, (1177, 846), PlayCountBase)
                    text_center_pos = (1359, 865)
                    _temp_img = self.TextDraw(_temp_img, str(play_count), text_center_pos,
                                              font_path=self.title_font_path,
                                              font_size=30, font_color=(248, 34, 117), h_align="center")
                    
                background = Image.alpha_composite(background, _temp_img)                           
        except Exception as e:
            print(f"Error generating achievement: {e}")
            print(traceback.format_exc())
            background = Image.new('RGBA', (1520, 500), (0, 0, 0, 255))
        return background
    

# 入口：生成单个成绩图片    
def generate_single_image(game_type, style_config, record_detail, output_path, title_text) -> Image.Image:
    # 查找对应游戏类型的style_config
    try:
        selected_style_config = None
        if isinstance(style_config, dict):
            selected_style_config = style_config
        elif isinstance(style_config, list):
            for i, sub_config in enumerate(style_config):
                if "type" in sub_config and sub_config["type"] == game_type:
                    selected_style_config = sub_config
                    break
            if selected_style_config is None:
                raise ValueError(f"No {game_type} style_config found in the provided list.")
        else:
            raise ValueError("style_config must be a dict or a list of dicts.")
        
    except Exception as e:
        raise ValueError(f"Error processing style_configs: {e}")
    
    if game_type == "maimai":
        function = MaiImageGenerater(style_config=selected_style_config)
        # 加载通用外框素材
        background_path = selected_style_config["asset_paths"]["score_image_base"]
        with Image.open(background_path) as background:
            # 生成并调整单个成绩图片
            single_image = function.GenerateOneAchievement(record_detail)
            new_size = (int(single_image.width * 0.55), int(single_image.height * 0.55))
            single_image = single_image.resize(new_size, Image.LANCZOS)
            
            # 粘贴图片
            background.paste(single_image, (940, 170), single_image.convert("RGBA"))
            
            # 添加标题文字
            draw = ImageDraw.Draw(background)
            font = ImageFont.truetype(function.font_path, 50)
            draw.text((940, 100), title_text, fill=(255, 255, 255), font=font)
            
            # 保存图片
            background.save(output_path)

        # 返回已保存的图片对象
        with Image.open(output_path) as final_img:
            return final_img.copy()
        
    elif game_type == "chunithm":
        function = ChuniImageGenerater(style_config=selected_style_config)
        single_image = function.GenerateOneAchievement(record_detail)

        # 添加标题文字
        single_image = function.TextDraw(single_image, title_text, (248, 1016), max_width=280,
                                        font_path=function.ui_font_path,
                                        font_size=32, font_color=(255, 255, 255), h_align="center")
        
        # 保存图片
        single_image.save(output_path)
        return single_image
    else:
        raise ValueError(f"Unsupported game type: {game_type}")

@DeprecationWarning
def check_mask_waring(acc_string, cnt, warned=False):
    if len(acc_string.split('.')[1]) >= 4 and acc_string.split('.')[1][-3:] == "000":
        cnt = cnt + 1
        if cnt > 5 and not warned:
            print(f"Warning： 检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。特殊情况请忽略。")
            warned = True
    return cnt, warned

# @DeprecationWarning
# def load_music_jacket(music_tag):
#     """从本地查找或从线上下载乐曲封面。仅用于maimaiDX。"""
#     if type(music_tag) == int:
#         image_path = f"jackets/maimaidx/Jacket_{music_tag}.jpg"
#     elif type(music_tag) == str:
#         # 判断music_tag字符串是否为正整数
#         if music_tag.isdigit():
#             music_id = int(music_tag)
#             image_path = f"jackets/maimaidx/Jacket_{music_id}.jpg"
#         else:
#             image_path = f"jackets/maimaidx/Jacket_N_{music_tag}.jpg"
#     else:
#         raise ValueError("music_tag must be an integer or string.")
#     try:
#         # print(f"正在获取乐曲封面{image_path}...")
#         jacket = download_image_data(image_path)
#         # 返回 RGBA 模式图像，并强制缩放到400*400px
#         return jacket.convert("RGBA").resize((400, 400), Image.LANCZOS)
#     # 抛出异常，默认封面由上层处理
#     except FileNotFoundError:
#         print(f"乐曲封面{image_path}不存在")
#         return None

# @DeprecationWarning
# def find_single_song_metadata(all_metadata, record_detail):
#     for music in all_metadata:
#         if music['id'] is not None and music['id'] == str(record_detail['song_id']):
#             return music
#         else:
#             # 对于未知id的新曲，必须使用曲名和谱面类型匹配
#             song_name = record_detail['title']
#             song_type = record_detail['type']
#             if song_name == music['name'] and CHART_TYPE_MAP_MAIMAI[song_type] == music['type']:
#                 return music
#     return None
