"""决策卡上的参数版本和假设开关。不改求解。"""
import csv
import hashlib
import json
import os

H = os.path.dirname(os.path.abspath(__file__))


def data_hash(data_dir=None):
    """data/ 里每个文件的路径和内容。短哈希，用来对上这一张卡用的是哪一包参数。"""
    root = data_dir or os.path.join(H, "data")
    digest = hashlib.sha1()
    paths = []
    for dirpath, _, files in os.walk(root):
        for name in files:
            if name.startswith("."):
                continue
            paths.append(os.path.join(dirpath, name))
    for path in sorted(paths):
        digest.update(os.path.relpath(path, root).encode())
        with open(path, "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:8]


def _blank(value):
    return value is None or str(value).strip() == ""


def _num(value):
    if _blank(value):
        return None
    return float(value)


def assumption_line(data_dir=None):
    """A05–A10 全是默认关闭时写明。有一项打开就点名，不把示例块算进去。"""
    root = data_dir or os.path.join(H, "data")
    coarse = {}
    with open(os.path.join(root, "coarse_params.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            coarse[row["key"]] = row["value"]
    with open(os.path.join(root, "daily_config.json"), encoding="utf-8") as f:
        daily = json.load(f)
    on = []
    if not _blank(coarse.get("head_up")) or not _blank(coarse.get("head_dn")) or (daily.get("hire_lead_months") or 0) >= 1:
        on.append("A05")
    if _num(coarse.get("post_switch_eff")) not in (None, 1.0) or (daily.get("learning_extra_lost_days") or 0) != 0:
        on.append("A06")
    with open(os.path.join(root, "jph_options.csv"), encoding="utf-8") as f:
        mix = [row.get("mix_eff", "1") for row in csv.DictReader(f)]
    if any(_num(x) not in (None, 1.0) for x in mix):
        on.append("A07")
    if not _blank(coarse.get("pm_days")) and _num(coarse.get("pm_days")) != 0 or (daily.get("pm_dates") or []):
        on.append("A08")
    if (_num(coarse.get("moq_fee")) or 0) != 0 or (daily.get("jit_swing_penalty_per_unit") or 0) != 0:
        on.append("A09")
    if (_num(coarse.get("restart_cost")) or 0) != 0 or (daily.get("restart_quality_cost") or 0) != 0:
        on.append("A10")
    if not on:
        return "假设开关：A05–A10 默认关闭"
    return "假设开关：已打开 " + "、".join(on)


def cross_scale_rows(data_dir=None):
    """月度层和按天层对不上、因此不能相加的科目。数字从表现读，不新求解。"""
    root = data_dir or os.path.join(H, "data")
    with open(os.path.join(root, "shop_params.csv"), encoding="utf-8") as f:
        shop = {row["shop"]: row for row in csv.DictReader(f)}
    with open(os.path.join(root, "daily_config.json"), encoding="utf-8") as f:
        daily = json.load(f)
    rows = []
    monthly = float(shop["BIW"]["buffer_cap"])
    daily_cap = float(daily["biw_buffer_max"])
    if monthly != daily_cap:
        rows.append(dict(科目="白车身缓存上限", 月度=f"{monthly:g} 台", 按天=f"{daily_cap:g} 台",
                         状态="未验证", 说明="各层用各层的上限，两层成本不能相加"))
    rows.append(dict(科目="借调净额", 月度="按人·天凑平", 按天="同一天开工时可以是 0",
                     状态="未验证", 说明="不进任何合计"))
    return rows
