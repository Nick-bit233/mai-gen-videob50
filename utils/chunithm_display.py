"""Display-only constants; never change archive ratings or ordering."""
import math
from utils.style_config import constant_mode


def valid_constant(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def archive_constants(metadata, level_index, fallback=None):
    from utils.DataUtils import get_level_value_from_chart_meta
    current = latest = strict_cn = strict_latest = None
    for chart in (metadata or {}).get("charts_info", []):
        if chart.get("difficulty", -1) == level_index:
            current = get_level_value_from_chart_meta(chart)
            latest = get_level_value_from_chart_meta(chart, latest_first=True)
            strict_cn = valid_constant(chart.get("level_value_cn"))
            strict_latest = valid_constant(chart.get("level_value_latest"))
    if current is None:
        current = fallback if fallback is not None else "--"
    return {"ds_cur": current, "ds_next": latest,
            "ds_cn": strict_cn, "ds_latest": strict_latest}


def display_constants(record, style):
    mode = constant_mode(style)
    if mode != "compare":
        value = valid_constant(record.get("ds_cn" if mode == "cn" else "ds_latest"))
        return {"mode": mode, "level": value,
                "columns": [(mode, str(value) if value is not None else "--", (1662, 1018))]}
    current, latest = record.get("ds_cur"), record.get("ds_next")
    cn, jp = valid_constant(current), valid_constant(latest)
    current_text = str(current) if cn is not None else "--"
    latest_text = "--" if jp is None else str(jp)
    if cn is not None and jp is not None:
        latest_text += "↑" if jp > cn else "↓" if jp < cn else "→"
    return {"mode": mode, "level": cn if cn is not None and cn > 1 else jp,
            "columns": [("cn", current_text, (1562, 1018)), ("latest", latest_text, (1756, 1018))]}
