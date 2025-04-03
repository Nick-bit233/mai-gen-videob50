import json
import os.path
import requests
from utils.DataUtils import download_metadata, get_image_data
from PIL import Image, ImageDraw, ImageFont

DATA_CONFIG_VERSION = "0.4"

class Utils:
    def __init__(self, InputUserID: int = 0):
        UserId = InputUserID
        if UserId != 0:
            try:
                with open(f"./b50_datas/{UserId}_B50.json") as file:
                    UserB50Data = json.load(file)
            except FileNotFoundError:
                print("错误：未找到 JSON 文件。")
                return {}
            except json.JSONDecodeError:
                print("错误：JSON 解码失败。")
                return {}

    def JacketLoader(self, MusicId):
        if type(MusicId) == int:
            image_path = f"jackets/Jackets/Jacket_{MusicId}.jpg"
        else:
            image_path = f"jackets/Jackets/Jacket_N_{MusicId}.jpg"
        try:
            print(f"正在获取乐曲封面{image_path}...")
            jacket = get_image_data(image_path)
            # 返回 RGBA 模式图像，并强制缩放到400*400px
            return jacket.convert("RGBA").resize((400, 400), Image.LANCZOS)
        except FileNotFoundError:
            print(f"获取乐曲封面{image_path}失败，将使用默认封面")
            with Image.open(f"./images/Jackets/UI_Jacket_000000.png") as jacket:
                return jacket.convert("RGBA")

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
            with Image.open(f'./images/Numbers/{str(level)}/{IntegerPart}.png') as Number:
                Background.paste(Number, (48, 60), Number)
        else:
            with Image.open(f'./images/Numbers/{str(level)}/1.png') as FirstNumber:
                Background.paste(FirstNumber, (18, 60), FirstNumber)
            with Image.open(f'./images/Numbers/{str(level)}/{IntegerPart[1]}.png') as SecondNumber:
                Background.paste(SecondNumber, (48, 60), SecondNumber)
        if len(DecimalPart) == 1:
            with Image.open(f'./images/Numbers/{str(level)}/{DecimalPart}.png') as Number:
                Number = Number.resize((32, 40), Image.LANCZOS)
                Background.paste(Number, (100, 79), Number)
        else:
            raise Exception("定数无效")

        # 加载加号
        if int(DecimalPart) >= 7:
            with Image.open(f"./images/Numbers/{str(level)}/plus.png") as PlusMark:
                Background.paste(PlusMark, (75, 50), PlusMark)

        return Background

    def TypeLoader(self, Type: str = "SD"):
        _type = Type
        with Image.open(f"./images/Types/{_type}.png") as _Type:
            _Type = _Type.resize((180, 50), Image.BICUBIC)
            return _Type.copy()

    def AchievementLoader(self, Achievement: str):
        IntegerPart = Achievement.split('.')[0]
        DecimalPart = Achievement.split('.')[1]

        Background = Image.new('RGBA', (800, 118), (0, 0, 0, 0))
        Background.convert("RGBA")

        for __index, __digit in enumerate(IntegerPart):
            with Image.open(f"./images/Numbers/AchievementNumber/{__digit}.png") as Number:
                Background.paste(Number, (__index * 78 + (3 - len(IntegerPart)) * 78, 0), Number)

        for __index, __digit in enumerate(DecimalPart):
            with Image.open(f"./images/Numbers/AchievementNumber/{__digit}.png") as Number:
                ScalLevel = 0.75
                Number = Number.resize((int(86 * ScalLevel), int(118 * ScalLevel)), Image.LANCZOS)
                Background.paste(Number, (270 + __index * int(86 * ScalLevel - 5), int(118 * (1 - ScalLevel) - 3)),
                                 Number)

        return Background

    def StarLoader(self, Star: int = 0):
        match Star:
            case _ if Star == 0:
                with Image.open("./images/Stars/0.png") as _star:
                    return _star.copy()
            case _ if Star == 1 or Star == 2:
                with Image.open("./images/Stars/1.png") as _star:
                    return _star.copy()
            case _ if Star == 3 or Star == 4:
                with Image.open("./images/Stars/3.png") as _star:
                    return _star.copy()
            case _ if Star == 5:
                with Image.open("./images/Stars/5.png") as _star:
                    return _star.copy()

    def ComboStatusLoader(self, ComboStatus: int = 0):
        match ComboStatus:
            case _ if ComboStatus == '' or ComboStatus is None:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))
            case _ if ComboStatus == 'fc':
                with Image.open("./images/ComboStatus/1.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if ComboStatus == 'fcp':
                with Image.open("./images/ComboStatus/2.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if ComboStatus == 'ap':
                with Image.open("./images/ComboStatus/3.png") as _comboStatus:
                    return _comboStatus.copy()
            case _ if ComboStatus == 'app':
                with Image.open("./images/ComboStatus/4.png") as _comboStatus:
                    return _comboStatus.copy()

    def SyncStatusLoader(self, SyncStatus: int = 0):
        match SyncStatus:
            case _ if SyncStatus == '' or SyncStatus is None:
                return Image.new('RGBA', (80, 80), (0, 0, 0, 0))
            case _ if SyncStatus == 'fs':
                with Image.open("./images/SyncStatus/1.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'fsp':
                with Image.open("./images/SyncStatus/2.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'fsd':
                with Image.open("./images/SyncStatus/3.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'fsdp':
                with Image.open("./images/SyncStatus/4.png") as _syncStatus:
                    return _syncStatus.copy()
            case _ if SyncStatus == 'sync':
                with Image.open("./images/SyncStatus/5.png") as _syncStatus:
                    return _syncStatus.copy()

    def TextDraw(self, Image, Text: str = "", Position: tuple = (0, 0)):
        # 文本居中绘制

        # 载入文字元素
        Draw = ImageDraw.Draw(Image)
        FontPath = "./font/FOT_NewRodin_Pro_EB.otf"
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
        with open(os.path.join(os.getcwd(), "music_datasets/all_music_infos.json"),
                  'r', encoding='utf-8') as f:
            music_info = json.load(f)
        # 匹配乐曲id和难度id找到谱面notes数量
        level_index = record_detail['level_index']
        song_id = record_detail['song_id']
        user_dx_score = record_detail['dxScore']
        max_dx_score = -1
        for music in music_info:
            if music['id'] == str(song_id):
                notes_list = music['charts'][level_index]['notes']
                max_dx_score = sum(notes_list) * 3
                break
        dx_stars = 0
        if max_dx_score == -1:
            print(f"未找到乐曲{song_id}的难度{level_index}的max dx score信息。")
            return dx_stars
        match user_dx_score:
            case _ if 0 <= user_dx_score < max_dx_score * 0.85:
                dx_stars = 0
            case _ if max_dx_score * 0.85 <= user_dx_score < max_dx_score * 0.9:
                dx_stars = 1
            case _ if max_dx_score * 0.9 <= user_dx_score < max_dx_score * 0.92:
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
        try:
            assert record_detail['level_index'] in range(0, 5)
            image_asset_path = os.path.join(os.getcwd(),
                                            f"images/AchievementBase/{record_detail['level_index']}.png")
            dx_stars = self.count_dx_stars(record_detail)
            with Image.open(image_asset_path) as Background:
                Background = Background.convert("RGBA")

                # 载入图片元素
                TempImage = Image.new('RGBA', Background.size, (0, 0, 0, 0))
                # 加载乐曲封面
                JacketPosition = (44, 53)
                Jacket = self.JacketLoader(MusicId=record_detail["song_id"])
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
                    with Image.open("./images/Playcount/PlayCountBase.png") as PlayCountBase:
                        TempImage.paste(PlayCountBase, (1170, 420), PlayCountBase)
                    TextCentralPosition = (1435, 458)
                    PlayCountText = str(PlayCount)
                    TempImage = self.TextDraw(TempImage, PlayCountText, TextCentralPosition)

                Background = Image.alpha_composite(Background, TempImage)

        except FileNotFoundError as e:
            print(e)

        return Background


def get_data_from_fish(username, params=None):
    """从水鱼获取数据"""
    if params is None:
        params = {}
    type = params.get("type", "maimai")
    query = params.get("query", "best")
    # MAIMAI DX 的请求
    if type == "maimai":
        if query == "best":
            url = "https://www.diving-fish.com/api/maimaidxprober/query/player"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json"
            }
            payload = {
                "username": username,
                "b50": "1"
            }
            response = requests.post(url, headers=headers, json=payload)
        elif query == "all":
            url = f"https://www.diving-fish.com/api/maimaidxprober/dev/player/records?username={username}"
            # Read developer token from config file
            if not os.path.exists("develop_token.txt"):
                FISH_DE_TOKEN = ""
            else:
                with open("develop_token.txt", "r", encoding='utf-8') as f:
                    content = f.readline().strip()
                    FISH_DE_TOKEN = content
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json",
                "Developer-Token": FISH_DE_TOKEN,
            }
            response = requests.get(url, headers=headers)
        elif query == "test_all":
            url = "https://www.diving-fish.com/api/maimaidxprober/player/test_data"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
        else:
            raise ValueError("Invalid filter type for MAIMAI DX")
    elif type == "chuni":
        raise NotImplementedError("Only MAIMAI DX is supported for now")
    else:
        raise ValueError("Invalid game data type for diving-fish.com")

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 400 or response.status_code == 403:
        msg = response.json().get("message", None)
        if not msg:
            msg = response.json().get("msg", "水鱼端未知错误")
        return {"error": f"用户校验失败，返回消息：{msg}"}
    else:
        return {"error": f"请求水鱼数据失败，状态码: {response.status_code}，返回消息：{response.json()}"}
