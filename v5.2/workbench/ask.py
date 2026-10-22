"""把中文问题收成旋钮。未确认不求解。解释只引用决策卡里已经出现的数。"""
import json, os, re
import workbench.api as api

SHOPS = (("冲压", "STP"), ("焊装", "BIW"), ("涂装", "PNT"), ("总装", "TCF"))
UP = "涨加多升"
DOWN = "降少跌减"
REFUSE = ("真实成本", "真实总", "明年工厂", "招聘提前", "实际总成本", "明年的真实")
DIALOGUE = os.path.join(api.OUT, "dialogue.jsonl")


def _factor(direction, amount):
    return round(1 + amount, 4) if direction in UP else round(1 - amount, 4)


def _amount(text):
    """返回 (方向字符, 比例 0.15)。找不到则 None。"""
    m = re.search(rf"([{UP}{DOWN}])\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        return m.group(1), float(m.group(2)) / 100
    word = {"半": 0.05, "一": 0.1, "两": 0.2, "三": 0.3}
    m = re.search(rf"([{UP}{DOWN}])\s*(半|一|两|三)成", text)
    if m:
        return m.group(1), word[m.group(2)]
    return None


def _months(text):
    m = re.search(r"(\d{1,2})\s*[到至\-–—]\s*(\d{1,2})\s*月", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= b <= 12:
            return list(range(a, b + 1))
    found = [int(x) for x in re.findall(r"(\d{1,2})\s*月", text)]
    return [m for m in found if 1 <= m <= 12]


def _shop(text):
    for name, code in SHOPS:
        if name in text:
            return code, name
    return None, None


def _library_hit(text):
    hits = [r for r in api.library() if r["name"] in text]
    if not hits:
        return None
    return max(hits, key=lambda r: len(r["name"]))


def _same(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


def _named(knobs):
    for row in api.library():
        if _same(row["knobs"], knobs):
            return row["name"]
    return "自定义"


def log_turn(record):
    os.makedirs(api.OUT, exist_ok=True)
    with open(DIALOGUE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse(text, pending=None):
    """status: confirm 待确认后运行；ask 还缺信息；refuse 模型覆盖不了。"""
    raw = (text or "").strip()
    if pending and pending.get("旋钮") and re.fullmatch(r"(确认|好|运行|就用这个|是|对)", raw):
        return dict(pending, 原文=raw)
    if pending and pending.get("缺") == "月份":
        months = _months(raw) or (_months("6月") if "就用" in raw and "6" in raw else [])
        if "就用" in raw and not months:
            months = [6]
        if len(months) == 1:
            code = pending["车间代码"]
            knobs = {"down": {f"{code}|{months[0]}": pending["天数"]}}
            name = _named(knobs)
            say = f"理解为「{pending['车间']} {months[0]} 月停 {pending['天数']} 个工作日」"
            if name != "自定义":
                say += f"，对应预置场景「{name}」"
            say += "。确认运行吗？"
            return dict(status="confirm", 说=say, 旋钮=knobs, 名称=name, 问题=pending.get("问题") or raw, 原文=raw)
    if any(w in raw for w in REFUSE):
        return dict(status="refuse", 旋钮={}, 名称="", 原文=raw,
                    说="当前模型用的是示例数据，不能给出真实成本，也没有招聘提前期。参数接入并完成对账之后才能回答绝对金额。我可以按示例参数演示某个场景相对基准的变化。")
    hit = _library_hit(raw)
    code, shop = _shop(raw)
    vague_stop = bool(code and "停" in raw and not _months(raw) and (not hit or hit["name"] not in raw))
    if hit and not vague_stop:
        say = f"我理解为预置场景「{hit['name']}」：{hit['description']}。配置仍是示例包。确认运行吗？"
        return dict(status="confirm", 说=say, 旋钮=hit["knobs"], 名称=hit["name"], 问题=raw, 原文=raw)
    if "停" in raw and ("周" in raw or "天" in raw or "工作日" in raw):
        days = 5 if "周" in raw else None
        m = re.search(r"(\d+)\s*个?\s*工作日", raw) or re.search(r"停\s*(\d+)\s*天", raw)
        if m:
            days = int(m.group(1))
        if days is None:
            return dict(status="ask", 原文=raw, 说="请问停几天？预置场景按 5 个工作日计算。")
        if not code:
            return dict(status="ask", 原文=raw, 说="请问是哪个车间停线？冲压、焊装、涂装还是总装。")
        if not _months(raw):
            hint = "预置场景「焊装停线一周」按 6 月停 5 个工作日。回复「就用 6 月」或直接说月份。" if code == "BIW" and days == 5 else "直接回复月份，例如「6 月」。"
            return dict(status="ask", 缺="月份", 车间=shop, 车间代码=code, 天数=days, 问题=raw, 原文=raw,
                        说=f"请问是哪个月？{hint}")
        knobs = {"down": {f"{code}|{m}": days for m in _months(raw)}}
        return dict(status="confirm", 旋钮=knobs, 名称=_named(knobs), 问题=raw, 原文=raw,
                    说=f"理解为「{shop} {'、'.join(str(m) for m in _months(raw))} 月停 {days} 天」。确认运行吗？")
    knobs = {}
    amt = _amount(raw)
    if amt and "电价" in raw:
        knobs["elec"] = _factor(*amt)
    if amt and "工资" in raw:
        knobs["wage"] = _factor(*amt)
    if amt and ("气价" in raw or "天然气" in raw):
        knobs["gas"] = _factor(*amt)
    if amt and "需求" in raw:
        factor = _factor(*amt)
        months = _months(raw)
        if months:
            knobs["demand_month"] = {str(m): factor for m in months}
        else:
            knobs["demand_all"] = factor
    if not knobs:
        return dict(status="ask", 旋钮={}, 名称="", 问题=raw, 原文=raw,
                    说="我还不能对应到场景。可以说预置场景的名字，或说「9到12月需求涨15%」「电价涨两成」「焊装6月停5天」。")
    bad = api.validate(knobs)
    if bad:
        return dict(status="refuse", 旋钮=knobs, 名称="", 原文=raw, 说="这个幅度超出工作台允许的范围：" + "；".join(bad))
    name = _named(knobs)
    bits = []
    if "demand_all" in knobs:
        bits.append(f"全年需求 ×{knobs['demand_all']}")
    if "demand_month" in knobs:
        months = "、".join(knobs["demand_month"])
        factor = next(iter(knobs["demand_month"].values()))
        bits.append(f"{months} 月需求 ×{factor}")
    for key, label in (("elec", "电价"), ("wage", "工资"), ("gas", "气价")):
        if key in knobs:
            bits.append(f"{label}系数 ×{knobs[key]}")
    say = "理解为「" + "，".join(bits) + "」"
    if name != "自定义":
        say += f"，对应预置场景「{name}」"
    say += "。确认运行吗？"
    return dict(status="confirm", 说=say, 旋钮=knobs, 名称=name, 问题=raw, 原文=raw)


def explain(card):
    """解释等于决策卡正文，因此每个数都已在结果里。"""
    s, b = card["本次"], card["基准"]
    delta = s["运营成本_万元"] - b["运营成本_万元"]
    lead = f"全年运营成本 {s['运营成本_万元']:,} 万元，比基准 {b['运营成本_万元']:,} 万元 {delta:+,} 万元。"
    text = lead + "\n\n" + card["正文"]
    missing = stray_numbers(text, card)
    if missing:
        text = card["正文"]
    return text


def stray_numbers(text, card):
    allowed = set(re.findall(r"\d+(?:\.\d+)?", json.dumps(card, ensure_ascii=False).replace(",", "")))
    allowed |= set(re.findall(r"\d+(?:\.\d+)?", card.get("正文", "").replace(",", "")))
    found = re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return [n for n in found if n not in allowed]
