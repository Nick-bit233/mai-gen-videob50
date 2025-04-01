import requests
import re
import os
import json
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

def getJacketUrls():
    global urlDict
    page = get('https://dxrating.net/search')
    pattern = r'dxdata-.*?\.js'
    matches = re.findall(pattern, page)
    # print(matches)
    if matches:
        dataAssetPath = f'music_datasets/jacketData-{matches[0][7:-3]}.json'
        if os.path.exists(dataAssetPath):
            print(f"读取本地封面地址配置{dataAssetPath}")
            with open(dataAssetPath, 'r', encoding='utf-8') as f:
                urlDict = json.loads(f.read())
            return

        print(f"没有找到本地配置，重新爬取至{dataAssetPath}")
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
        print(f"成功爬取{len(songIdList)}张封面地址")
        with open(dataAssetPath, 'w', encoding='utf-8') as f:
            f.write(json.dumps(urlDict, ensure_ascii=False))
    else:
        print('没有找到dxdata')

def getJacket(songName):
    if songName not in urlDict:
        print(f'没有找到歌曲{songName}')
        return None
    
    imgId = urlDict[songName]
    jacketCachePath = f'images/JacketCache/{imgId}.png'
    if os.path.exists(jacketCachePath):
        print(f"找到了歌曲{songName}封面的本地缓存")
        return Image.open(jacketCachePath)
    
    retryTimes = 5
    for i in range(retryTimes):
        try:
            response = requests.get(f'https://shama.dxrating.net/images/cover/v2/{urlDict[songName]}.jpg')
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert('RGBA')
            print(f"爬取了歌曲{songName}的封面")
            img.save(jacketCachePath)
            return img
        except requests.exceptions.RequestException as e:
            print(f"请求歌曲{songName}的封面时发生网络错误：{e}")
            print(f"剩余{retryTimes - i - 1}次重试...")    
    return None

getJacketUrls()