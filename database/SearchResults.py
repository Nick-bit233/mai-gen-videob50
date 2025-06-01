import os
from utils.PageUtils import load_record_config, save_record_config

class SearchResults:
    def __init__(self, file_path: str, username: str = ""):
        self.file_path = file_path
        self.results = []
        self.map = {} # (song_id, level_index) => index in self.results

        if os.path.exists(file_path):
            # 加载已有的搜索结果
            self.results = load_record_config(file_path, username)

            # 创建索引映射
            for index, result in enumerate(self.results):
                song_id = result.get("song_id")
                level_index = result.get("level_index")
                
                if song_id is None or level_index is None:
                    # ignore broken items
                    # TODO: add log to report this warning
                    continue
                else:
                    self.map[(song_id, level_index)] = index
        else:
            # 创建一个只包含 {"records": []} 的 json 文件
            self.dump_to_file()

    def __del__(self):
        # 在对象销毁时保存结果到文件
        self.dump_to_file()

    def add_result(self, result):
        self.results.append(result)

    def get_item(self, song):
        index = self.map.get((song['song_id'], song['level_index']), -1)
        return self.results[index] if index != -1 else None
    
    def update_item(self, song, new_result):
        index = self.map.get((song['song_id'], song['level_index']), -1)
        if index != -1:
            self.results[index] = new_result
        else:
            self.results.append(new_result)
            self.map[(song['song_id'], song['level_index'])] = len(self.results) - 1
    
    def dump_to_file(self):
        save_record_config(self.file_path, self.results)
