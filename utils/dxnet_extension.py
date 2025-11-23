from utils.PageUtils import load_music_metadata

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

# Compute DX rating for a single song
def compute_rating(ds, score):
    return int(ds * min(score, 100.5) * get_factor(score))

# Compute Chunithm rating for a single song
def compute_chunithm_rating(ds, score):
    try:
        s = int(float(score))
    except Exception:
        raise ValueError("Failed to parse chunithm score.")

    tiers = [
        (1_009_000, None,        ('fixed', 2.15)),
        (1_007_500, 1_009_000,   ('step',  2.00, 100, 0.01, 2.15)),
        (1_005_000, 1_007_500,   ('step',  1.50, 50,  0.01, 2.00)),
        (1_000_000, 1_005_000,   ('step',  1.00, 100, 0.01, 1.50)),
        (990_000,   1_000_000,   ('step',  0.60, 250, 0.01, 1.00)),
        (975_000,   990_000,     ('step',  0.00, 250, 0.01, 0.60)),
        (950_000,   975_000,     ('fixed', -1.5)),
        (925_000,   950_000,     ('fixed', -3.0)),
        (900_000,   925_000,     ('fixed', -5.0)),
        (800_000,   900_000,     ('func',  lambda ds, s: (ds - 5.0) / 2.0)),
    ]

    for mn, mx, rule in tiers:
        if s >= mn and (mx is None or s < mx):
            typ = rule[0]
            if typ == 'fixed':
                return round(ds + rule[1], 2)
            if typ == 'func':
                return round(rule[1](ds, s), 2)
            # 'step'
            base, step_pts, step_val, cap = rule[1], rule[2], rule[3], rule[4]
            steps = max(0, (s - mn) // step_pts)
            extra = min(steps * step_val, cap - base)
            return round(ds + base + extra, 2)

    return 0.0

def parse_level(ds):
    return f"{int(ds)}+" if int((ds * 10) % 10) >= 6 else str(int(ds))

class ChartManager:
    
    def __init__(self, compute_total_rating = True):
        self.all_songs = []
        self.results = []
        self.compute_total_rating = compute_total_rating
        self.total_rating = 0

        # with open("./music_datasets/jp_songs_info.json", 'r', encoding="utf-8") as f:
        self.all_songs = load_music_metadata("maimaidx")    

    def fill_json(self, chart_json):
        #chart = {
        #     "achievements": number, # given
        #     "ds": number, # search
        #     "dxScore": number,
        #     "fc": str,
        #     "fs": str,
        #     "level": str, # might given
        #     "level_index": number, # given
        #     "level_label": str, # given
        #     "ra": number, # compute
        #     "rate": str, # compute
        #     "song_id": number, # search
        #     "title": str, # given
        #     "type": str # given
        # }

        # Parse rate
        chart_json["rate"] = get_rate(chart_json["achievements"])

        chart_title = chart_json["title"]
        chart_type = 1 if chart_json["type"].lower() == "dx" else 0
        chart_level_index = chart_json["level_index"]

        matched_song = self.find_song(chart_title, chart_type)
        song_rating = 0
        
        # Extract info from matched json object
        if matched_song:
            if ("id" in matched_song) and (matched_song["id"] is not None):
                chart_json["song_id"] = matched_song["id"]
            if chart_json["song_id"] is None or chart_json["song_id"] < 0:
                print(f"Info: can't resolve ID for song {chart_title}.")
            ds = matched_song["charts"][chart_level_index]["level"]
            chart_json["ds"] = ds
            song_rating = compute_rating(ds, chart_json["achievements"])
            chart_json["ra"] = song_rating
            if chart_json["level"] == "0": # data from dxrating.net doesn't provide a level                    
                chart_json["level"] = parse_level(ds)
        else:
            print(f"Warning: song {chart_title} with chart type {chart_json['type']} not found in dataset. Skip filling details.")
            # Default internal level as .0 or .6(+). Need extra dataset to specify.
            chart_level = chart_json["level"]
            ds = float(chart_level.replace("+", ".6") if "+" in chart_level else f"{chart_level}.0")
            chart_json["ds"] = ds
            song_rating = compute_rating(ds, chart_json["achievements"])
            chart_json["ra"] = song_rating

        if self.compute_total_rating:
            self.total_rating += song_rating

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
            if matched_song:
                self.results.append(matched_song)
            # print(f"Info: song {chart_title} with chart type {chart_type} found and cached.")
        
        return matched_song
            
