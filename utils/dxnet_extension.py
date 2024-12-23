import json

# Parse achievement to rate name
def get_rate(achievement):
    rates = [
        (100.5, "sssp"),
        (100, "sss"),
        (99.5, "ssp"),
        (99, "ss"),
        (98, "sp"),
        (97, "s"),
        (94, "aaa"),
        (90, "aa"),
        (80, "a"),
        (75, "bbb"),
        (70, "bb"),
        (60, "b"),
        (50, "c"),
        (0, "d")
    ]
    
    for threshold, rate in rates:
        if achievement >= threshold:
            return rate
    return "d"

# DX rating factors
def get_factor(achievement):
    factors = [
        (100.5, 0.224),
        (100.4999, 0.222),
        (100, 0.216),
        (99.9999, 0.214),
        (99.5, 0.211),
        (99, 0.208),
        (98.9999, 0.206),
        (98, 0.203),
        (97, 0.2),
        (96.9999, 0.176),
        (94, 0.168),
        (90, 0.152),
        (80, 0.136),
        (79.9999, 0.128),
        (75, 0.12),
        (70, 0.112),
        (60, 0.096),
        (50, 0.08),
        (0, 0.016)
    ]
    
    for threshold, factor in factors:
        if achievement >= threshold:
            return factor
    return 0

class ChartManager:
    
    def __init__(self):
        self.all_songs = []
        self.results = []

        with open("./music_datasets/jp_songs_info.json", 'r', encoding="utf-8") as f:
            self.all_songs = json.load(f)

    def fill_json(self, chart_json):
        #chart = {
        #     "achievements": number, # given
        #     "ds": number, # search
        #     "dxScore": number,
        #     "fc": str,
        #     "fs": str,
        #     "level": str, # given
        #     "level_index": number, # given
        #     "level_label": str, # given
        #     "ra": number, # compute
        #     "rate": str, # given
        #     "song_id": number, # search
        #     "title": str, # given
        #     "type": str # given
        # }
        chart_title = chart_json["title"]
        chart_type = 1 if chart_json["type"].lower() == "dx" else 0
        chart_level = chart_json["level_index"]

        matched_song = self.find_song(chart_title, chart_type)
        
        # Extract info from matched json object
        if matched_song:
            print(f"Info: song {chart_title} with chart type {chart_json['type']} found and cached.")
            self.results.append(matched_song)
            if "id" in matched_song:
                chart_json["song_id"] = matched_song["id"]
            if chart_json["song_id"] is None or chart_json["song_id"] < 0:
                print(f"Info: can't resolve ID for song {chart_title}.")
            chart_json["ds"] = matched_song["charts"][chart_level]["level"]
            chart_json["ra"] = int(chart_json["ds"] * chart_json["achievements"] * get_factor(chart_json["achievements"]))
        else:
            print(f"Warning: song {chart_title} with chart type {chart_json['type']} not found in dataset. Skip filling details.")
            # Default internal level as .0 or .6(+). Need external dataset to specify.
            chart_level = chart_json["level"]
            chart_json["ds"] = float(chart_level.replace("+", ".6") if "+" in chart_level else f"{chart_level}.0")   

        return chart_json

    def find_song(self, chart_title, chart_type):
        # Search in cached results first to save time
        matched_song = next(
            (entry for entry in self.results if entry.get("name") == chart_title and entry.get("type") == chart_type),
            None
        )

        if matched_song:
            print(f"Info: song {chart_title} with chart type {chart_type} found in cached results.")
        else:
            matched_song = next(
                (entry for entry in self.all_songs if entry.get("name") == chart_title and entry.get("type") == chart_type),
                None
            )
        
        return matched_song
            
