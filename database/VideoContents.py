import os
from utils.PageUtils import load_video_config, save_video_config

class VideoContents:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.intro = []
        self.ending = []
        self.main = []
        self.map = {}  # (song_id, level_index) => index in self.main

        json_data = load_video_config(file_path)
        if json_data:
            self.intro = json_data.get("intro", [])
            self.ending = json_data.get("ending", [])
            self.main = json_data.get("main", [])

            # 创建索引映射
            for index, item in enumerate(self.main):
                song_id = item.get("song_id")
                level_index = item.get("level_index")
                
                if song_id is None or level_index is None:
                    # 忽略损坏的条目
                    continue
                else:
                    self.map[(song_id, level_index)] = index
        else:
            # 创建一个只包含 {"intro": [], "ending": [], "main": []} 的 json 文件
            self.dump_to_file()

    def get_item(self, song):
        index = self.map.get((song['song_id'], song['level_index']), -1)
        return self.main[index] if index != -1 else None
    
    def update_item(self, song, new_item):
        index = self.map.get((song['song_id'], song['level_index']), -1)
        if index != -1:
            self.main[index] = new_item
        else:
            self.main.append(new_item)
            self.map[(song['song_id'], song['level_index'])] = len(self.main) - 1

    def dump_to_file(self):
        save_video_config(self.file_path, {
            "intro": self.intro,
            "ending": self.ending,
            "main": self.main
        })
