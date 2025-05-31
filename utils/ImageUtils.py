import json
import os.path
import traceback

from utils.DataUtils import download_image_data, CHART_TYPE_MAP_MAIMAI
from utils.PageUtils import load_music_metadata
from PIL import Image, ImageDraw, ImageFont

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
        if int(DecimalPart) >= 7:
            with Image.open(f"{self.image_root_path}/Numbers/{str(level)}/plus.png") as PlusMark:
                Background.paste(PlusMark, (75, 50), PlusMark)

        return Background

    def TypeLoader(self, Type: str = "SD"):
        _type = Type
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

    def ComboStatusLoader(self, ComboStatus: int = 0):
        match ComboStatus:
            case _ if ComboStatus == '' or ComboStatus is None:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))
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

    def SyncStatusLoader(self, SyncStatus: int = 0):
        match SyncStatus:
            case _ if SyncStatus == '' or SyncStatus is None:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))
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

    def count_dx_stars(self, record_detail: dict):
        # 计算DX星数
        music_info = load_music_metadata()
        # 匹配乐曲id和难度id找到谱面notes数量
        level_index = int(record_detail['level_index'])
        song_id = record_detail['song_id']
        user_dx_score = record_detail['dxScore']

        dx_stars = 0
        song_metadata = find_single_song_metadata(music_info, record_detail)
        if song_metadata is None:
            print(f"未找到乐曲{song_id}的难度{level_index}的max dx score信息。")
            return dx_stars
        else:
            notes_list = song_metadata['charts'][level_index]['notes']
            # 去除notes_list中的None值（sd谱中含有）
            notes_list = [note for note in notes_list if note is not None]
            max_dx_score = sum(notes_list) * 3

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
        """生成单个成绩记录。

        Args:
            record_detail (dict): 成绩记录详情，包含以下字段：
                - title (str): 乐曲标题
                - level (int): 等级整数
                - ds (float): 定数
                - level_index (int): 难度颜色
                - song_id (str): 乐曲ID
                - type (str): 谱面类型
                - achievements (float): 达成率
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
            dx_stars = self.count_dx_stars(record_detail)
            with Image.open(image_asset_path) as Background:
                Background = Background.convert("RGBA")

                # 载入图片元素
                TempImage = Image.new('RGBA', Background.size, (0, 0, 0, 0))

                # 加载乐曲封面
                JacketPosition = (44, 53)
                Jacket = load_music_jacket(music_tag=record_detail["song_id"])
                if Jacket is None:
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
                if "playCount" in record_detail:
                    PlayCount = record_detail["playCount"]
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


def generate_single_image(style_config, record_detail, output_path, title_text):
    if style_config is None or not isinstance(style_config, dict):
            raise ValueError("No valid style_config provided. Please provide a dictionary.")
    function = MaiImageGenerater(style_config=style_config)
    background_path = style_config["asset_paths"]["score_image_base"]
    with Image.open(background_path) as background:
        # 生成并调整单个成绩图片
        single_image = function.GenerateOneAchievement(record_detail)
        new_size = (int(single_image.width * 0.55), int(single_image.height * 0.55))
        single_image = single_image.resize(new_size, Image.LANCZOS)
        
        # 粘贴图片
        background.paste(single_image, (940, 170), single_image.convert("RGBA"))
        
        # 添加文字
        draw = ImageDraw.Draw(background)
        font = ImageFont.truetype(function.font_path, 50)
        draw.text((940, 100), title_text, fill=(255, 255, 255), font=font)
        
        # 保存图片
        background.save(output_path)


def check_mask_waring(acc_string, cnt, warned=False):
    if len(acc_string.split('.')[1]) >= 4 and acc_string.split('.')[1][-3:] == "000":
        cnt = cnt + 1
        if cnt > 5 and not warned:
            print(f"Warning： 检测到多个仅有一位小数精度的成绩，请尝试取消查分器设置的成绩掩码以获取精确成绩。特殊情况请忽略。")
            warned = True
    return cnt, warned


def load_music_jacket(music_tag):
    if type(music_tag) == int:
        image_path = f"jackets/maimaidx/Jacket_{music_tag}.jpg"
    elif type(music_tag) == str:
        # 判断music_tag字符串是否为正整数
        if music_tag.isdigit():
            music_id = int(music_tag)
            image_path = f"jackets/maimaidx/Jacket_{music_id}.jpg"
        else:
            image_path = f"jackets/maimaidx/Jacket_N_{music_tag}.jpg"
    else:
        raise ValueError("music_tag must be an integer or string.")
    try:
        # print(f"正在获取乐曲封面{image_path}...")
        jacket = download_image_data(image_path)
        # 返回 RGBA 模式图像，并强制缩放到400*400px
        return jacket.convert("RGBA").resize((400, 400), Image.LANCZOS)
    # 抛出异常，默认封面由上层处理
    except FileNotFoundError:
        print(f"乐曲封面{image_path}不存在")
        return None


def find_single_song_metadata(all_metadata, record_detail):
    for music in all_metadata:
        if music['id'] is not None and music['id'] == str(record_detail['song_id']):
            return music
        else:
            # 对于未知id的新曲，必须使用曲名和谱面类型匹配
            song_name = record_detail['title']
            song_type = record_detail['type']
            if song_name == music['name'] and CHART_TYPE_MAP_MAIMAI[song_type] == music['type']:
                return music
    return None