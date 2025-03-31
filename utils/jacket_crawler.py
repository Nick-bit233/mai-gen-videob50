import requests
import re
from PIL import Image
from io import BytesIO

def get(url):
    try:
        x = requests.get(url)
        x.raise_for_status()
        return x.text
    except requests.exceptions.RequestException as e:
        print(f"请求{url}失败：{e}")
    return None


urlDict = {}

def getJacketUrl():
    page = get('https://dxrating.net/search')
    pattern = r'dxdata-.*?\.js'
    matches = re.findall(pattern, page)
    # print(matches)
    if matches:
        jsFile = get(f'https://dxrating.net/assets/{matches[0]}')
        #with open('dxdata.js', 'w', encoding="utf-8") as f:
        #    f.write(jsFile)
        jsFile = jsFile[jsFile.find("[{songId:"):]
        jsFile = jsFile[:jsFile.find(',a=[{category:')]
        #with open('dxdata-filtered.js', 'w', encoding="utf-8") as f:    
        #    f.write(jsFile)
        #print("Write Done")
        
        songIdPattern = r'\bsongId:(["\'`])(?:\\.|(?!\1).)*\1'
        songImagePattern = r'imageName:".*?"'
        songIdList = []
        songImageList = re.findall(songImagePattern, jsFile)
        for match in re.finditer(songIdPattern, jsFile):
            songIdList.append(match.group()[7:])
        #with open('songIds.json', 'w', encoding='utf-8') as f:
        #    f.write(songIdList.__str__())
        #print(f'songIdList: {len(songIdList)}')
        #print(f'songImageList: {len(songImageList)}')
        for i in range(len(songIdList)):
            urlDict[songIdList[i][1:-1]] = songImageList[i][11:-1]
        print(f"成功获取{len(songIdList)}张封面地址")
        # with open('imagesUrl.json', 'w', encoding='utf-8') as f:
        #     f.write(json.dumps(urlDict, ensure_ascii=False))
    else:
        print('没有找到dxdata')

def getJacket(songName):
    if songName not in urlDict:
        print(f'没有找到歌曲{songName}的封面')
        return None
    
    try:
        response = requests.get(f'https://shama.dxrating.net/images/cover/v2/{urlDict[songName]}.jpg')
        if response.status_code == 200:
            return Image.open(BytesIO(response.content)).convert('RGBA')
        else:
            print(f"歌曲{songName}的封面请求失败，状态码：{response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"请求歌曲{songName}的封面时发生网络错误：{e}")
        return None

getJacketUrl()

if __name__ == '__main__':
    with open("jacketData.json", 'w', encoding='utf-8') as f:
        f.write(urlDict.__str__())