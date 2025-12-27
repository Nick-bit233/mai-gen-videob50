"""
常量定义模块
"""

# GPU硬件加速渲染方法配置
HARD_RENDER_METHOD = {
    "NVIDIA": {
        "hwaccel": "cuda",
        "codec": "nvenc"
    },
    "AMD": {
        "hwaccel": "amf", 
        "codec": "amf"
    },
    "Intel": {
        "hwaccel": "qsv",
        "codec": "qsv"
    }
}

# 获取数据类型（用于中二节奏）
CHUNI_DATA_TYPE = {
    "lxns": {
        "全都要": ["data.bests", "data.new_bests"],
        "仅旧曲": "data.bests",
        "仅新曲": "data.new_bests"
    },
    "fish": {
        "全都要": ["records.b30", "records.n20"],
        "仅旧曲": "records.b30",
        "仅新曲": "records.n20"
    }
}

