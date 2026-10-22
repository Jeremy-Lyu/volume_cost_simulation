"""工厂判断用的情景分析（示例数据）。

在基准月度模型上扫需求、车型、供应、停线、产能折扣、价格、管理约束和假设，
对照基准（或指定参照）看：运营成本、交付、班次/JPH 是否改、靠什么吸收。
运行：python3 factory_analysis.py
推到极限是开关，默认关。打开：data/switches.csv 里 extreme 写 1，或加上 --extreme。
结果写到 output/analysis/cases.csv、findings.csv 和 决策说明.md。
"""
import os, csv, sys
import multiprocessing as mp
import data_loader as dl
import engine
from scenarios import apply_knobs, load_library

H = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(H, "output", "analysis")
SN = {"STP": "冲压", "BIW": "焊装", "PNT": "涂装", "TCF": "总装"}
TIME_LIMIT = 60

def _month_total(d):
    tot = {}
    for (t, m), v in d["demand"].items(): tot[t] = tot.get(t, 0) + v
    return tot

def catalog(base, extreme=False):
    """一组工厂会拿来拍板的问题。extreme 为真时再加订单减半到翻倍、办法组合、坏事叠加和假设冲击。"""
    tot = _month_total(base)
    peak = max(tot, key=tot.get); trough = min(tot, key=tot.get)
    models = list(base["models"]); months = list(base["months"])
    cases = []
    def add(qid, question, name, knobs=None, build=None, against="基准", axis="", level=""):
        cases.append(dict(qid=qid, 问题=question, name=name, knobs=knobs or {}, build=build or {},
                          against=against, axis=axis, level=level))
    add("ref", "对照", "基准", against="")
    q = "需求偏离到什么程度，排产和交付才变？"
    core = (0.8, 0.85, 0.9, 1.1, 1.2, 1.3, 1.32, 1.35, 1.38, 1.4)
    tail = (0.5, 0.6, 1.5, 1.6, 1.8, 2.0) if extreme else ()
    for f in core + tail:
        add("demand", q, f"需求×{f:g}", {"demand_all": f}, axis="需求系数", level=f)
    q = "单月淡旺季扭曲，是提前做、加开班，还是延期？"
    add("shape", q, f"{peak}月需求+30%", {"demand_month": {str(peak): 1.3}})
    add("shape", q, f"{trough}月需求-40%", {"demand_month": {str(trough): 0.6}})
    q = "车型结构变了，瓶颈车间变不变？"
    add("mix", q, f"{models[0]}全年+35%", {"demand_model": {models[0]: 1.35}})
    if len(models) > 2:
        add("mix", q, f"{models[-1]}全年+50%", {"demand_model": {models[-1]: 1.5}})
    q = "零件供应缺口会变成交付缺口，还是用前后月消化？"
    add("supply", q, f"{models[1] if len(models)>1 else models[0]}在4-6月供应55%",
        {"supply": {f"{models[1] if len(models)>1 else models[0]}|{t}": 0.55 for t in (4, 5, 6)}})
    add("supply", q, f"{peak}月全车型供应70%", {"supply": {f"{m}|{peak}": 0.7 for m in models}})
    q = "哪个车间停线最贵，靠加班、预产还是延期补？"
    for s in base["shops"]:
        add("down", q, f"{SN.get(s, s)}{peak}月停5天", {"down": {f"{s}|{peak}": 5}}, axis="停线5天", level=s)
    add("down", q, f"涂装{peak}月停8天", {"down": {f"PNT|{peak}": 8}})
    q = "开动率、OEE、一次合格率、出勤，在现有口径里是不是同一件事？"
    # FTT 在模型里按车间、不按月。四条都打在涂装全年，才能看出是不是同一个产能折扣。
    add("factor", q, "涂装全年开动率×0.85", {"avail": {f"PNT|{t}": 0.85 for t in months}})
    add("factor", q, "涂装全年OEE×0.85", {"oee": {f"PNT|{t}": 0.85 for t in months}})
    add("factor", q, "涂装全年FTT=0.85", {"ftt": {"PNT": 0.85}})
    add("factor", q, "涂装全年出勤85%", {"attendance": {f"PNT|{t}": 0.85 for t in months}})
    add("factor", q, "2-3月全厂开动率×0.85", {"avail": {"ALL|2": 0.85, "ALL|3": 0.85}})
    add("factor", q, "7-8月全厂开动率×0.75", {"avail": {"ALL|7": 0.75, "ALL|8": 0.75}})
    add("factor", q, "1-3月涂装和总装爬坡0.7", {"ramp": {f"{s}|{t}": 0.7 for s in ("PNT", "TCF") for t in (1, 2, 3)}})
    q = "电价、工资、气价、夜班补贴会不会改班次？"
    add("price", q, "电价+30%", {"elec": 1.3})
    add("price", q, "工资+12%", {"wage": 1.12})
    add("price", q, "气价+50%", {"gas": 1.5})
    add("price", q, "夜班补贴×3", {"night_mul": 3})
    add("price", q, "电价+20%且工资+8%", {"elec": 1.2, "wage": 1.08})
    q = "管理约束各自的代价：多花多少，交付还保不保得住？"
    add("policy", q, "禁止三班", {"max_shifts": 2})
    add("policy", q, "加班上限24小时", {"ot": 24})
    add("policy", q, "人数月变化≤5%", build={"head_change": 0.05})
    add("policy", q, "几乎不能加人", build={"head_up": 0.02, "head_dn": 0.15})
    add("policy", q, "节拍每月最多一档且班次按季锁定", build={"jph_step": True, "shift_quarter": True})
    add("policy", q, "正常班利用率≤85%", build={"util_cap": 0.85})
    add("policy", q, "禁止跨车间借调", {"borrow": 0})
    add("policy", q, "换档一次200万", {"switch_cost": 2_000_000})
    add("policy", q, "需求×1.2且缓存×0.4", {"demand_all": 1.2, "buffer": 0.4}, against="需求×1.2")
    # 基准几乎不用第三班，约束看起来很便宜。增产到 ×1.2 才是这些规矩的真实价钱。
    ref12 = "需求×1.2"
    add("policy", q, "需求×1.2且禁止三班", {"demand_all": 1.2, "max_shifts": 2}, against=ref12)
    add("policy", q, "需求×1.2且加班上限24小时", {"demand_all": 1.2, "ot": 24}, against=ref12)
    add("policy", q, "需求×1.2且几乎不能加人", {"demand_all": 1.2}, {"head_up": 0.02, "head_dn": 0.15}, against=ref12)
    add("policy", q, "需求×1.2且正常班利用率≤85%", {"demand_all": 1.2}, {"util_cap": 0.85}, against=ref12)
    add("policy", q, "需求×1.2且禁止借调", {"demand_all": 1.2, "borrow": 0}, against=ref12)
    q = "需求加到开始丢单时，多出来的产能加在哪个车间才找得回？"
    for s in base["shops"]:
        add("neck", q, f"需求×1.4且{SN.get(s, s)}产能+15%",
            {"demand_all": 1.4, "avail": {f"{s}|{t}": 1.15 for t in months}}, against="需求×1.4")
    add("neck", q, "需求×1.4且四车间产能+15%",
        {"demand_all": 1.4, "avail": {f"ALL|{t}": 1.15 for t in months}}, against="需求×1.4")
    add("neck", q, "需求×1.4且车型月上限+15%", {"demand_all": 1.4, "cap_mul": 1.15}, against="需求×1.4")
    add("neck", q, "需求×1.4且成品库800元", {"demand_all": 1.4, "fg_hold": 800}, against="需求×1.4")
    q = "低负荷时，派遣比、停工发薪、换档成本改不改变开停结论？"
    ref = "需求×0.85"
    add("assume", q, "需求×0.85且派遣0%", {"demand_all": 0.85, "dispatch": 0}, against=ref)
    add("assume", q, "需求×0.85且派遣50%", {"demand_all": 0.85, "dispatch": 0.5}, against=ref)
    add("assume", q, "需求×0.85且停工日照发全薪", {"demand_all": 0.85, "stop_pay": 1}, against=ref)
    add("assume", q, "需求×0.85且换档免费", {"demand_all": 0.85, "switch_cost": 0, "switch_days": 0}, against=ref)
    add("assume", q, "需求×0.85且关闭停工日", {"demand_all": 0.85, "no_flex": True}, against=ref)
    q = "保交付的惩罚要多高，模型才不肯丢单？"
    add("penalty", q, "需求×1.25惩罚3万", {"demand_all": 1.25, "penalty": 30000})
    add("penalty", q, "需求×1.25惩罚0.3万", {"demand_all": 1.25, "penalty": 3000}, against="需求×1.25惩罚3万")
    add("penalty", q, "需求×1.25惩罚20万", {"demand_all": 1.25, "penalty": 200000}, against="需求×1.25惩罚3万")
    # ×1.25 仍然能交完，惩罚不起作用。真正要看的是已经出现流失的 ×1.4。
    add("penalty", q, "需求×1.4惩罚0.3万", {"demand_all": 1.4, "penalty": 3000}, against="需求×1.4")
    add("penalty", q, "需求×1.4惩罚20万", {"demand_all": 1.4, "penalty": 200000}, against="需求×1.4")
    q = "业务场景库里的冲击，工厂实际怎么接？"
    for sc in load_library():
        add("library", q, sc["name"], sc["knobs"])
    q = "几件事叠在一起时，单因素结论还成不成立？"
    add("combo", q, f"{peak}月冲量+涂装停3天+电价+20%",
        {"demand_month": {str(peak): 1.2}, "down": {f"PNT|{peak}": 3}, "elec": 1.2})
    if extreme:
        _extreme_cases(add, peak, trough, models, months)
    return cases

def _extreme_cases(add, peak, trough, models, months):
    """推到极限才加入的情景。参照都在本函数或常规情景里。"""
    q = "几套办法放在一起，哪套最省钱还能把车交上？"
    faster = lambda f: {f"ALL|{t}": f for t in months}
    # ×1.4 的月度缺口大约要放宽 8% 才盖得住。扫 5/8/10，看最少改多少。
    for pct, mul in ((5, 1.05), (8, 1.08), (10, 1.10)):
        add("bundle", q, f"需求×1.4且月上限+{pct}%", {"demand_all": 1.4, "cap_mul": mul}, against="需求×1.4")
    add("bundle", q, "需求×1.4且仓库200元", {"demand_all": 1.4, "fg_hold": 200}, against="需求×1.4")
    add("bundle", q, "需求×1.4且仓库2000元", {"demand_all": 1.4, "fg_hold": 2000}, against="需求×1.4")
    add("bundle", q, "需求×1.4且上限+15%但不许夜班",
        {"demand_all": 1.4, "cap_mul": 1.15, "max_shifts": 2}, against="需求×1.4")
    add("bundle", q, "需求×1.4且仓库800且不许夜班",
        {"demand_all": 1.4, "fg_hold": 800, "max_shifts": 2}, against="需求×1.4")
    add("bundle", q, "需求×1.4且仓库800且四线加快15%",
        {"demand_all": 1.4, "fg_hold": 800, "avail": faster(1.15)}, against="需求×1.4")
    # ×1.6 单靠放宽 15% 已经盖不住每月上限，看要不要把改表、加快、仓库叠在一起。
    ref16 = "需求×1.6"
    add("bundle", q, "需求×1.6且月上限+25%", {"demand_all": 1.6, "cap_mul": 1.25}, against=ref16)
    add("bundle", q, "需求×1.6且四线加快15%", {"demand_all": 1.6, "avail": faster(1.15)}, against=ref16)
    add("bundle", q, "需求×1.6且仓库800元", {"demand_all": 1.6, "fg_hold": 800}, against=ref16)
    add("bundle", q, "需求×1.6且上限+25%且四线加快15%",
        {"demand_all": 1.6, "cap_mul": 1.25, "avail": faster(1.15)}, against=ref16)
    add("bundle", q, "需求×1.6且上限+25%且仓库800",
        {"demand_all": 1.6, "cap_mul": 1.25, "fg_hold": 800}, against=ref16)
    add("bundle", q, "需求×1.6且上限四线仓库一起上",
        {"demand_all": 1.6, "cap_mul": 1.25, "avail": faster(1.15), "fg_hold": 800}, against=ref16)
    add("bundle", q, "需求×1.6且上限+25%但不许夜班",
        {"demand_all": 1.6, "cap_mul": 1.25, "max_shifts": 2}, against=ref16)
    ref2 = "需求×2"
    add("bundle", q, "需求×2且月上限+60%", {"demand_all": 2, "cap_mul": 1.6}, against=ref2)
    add("bundle", q, "需求×2且上限+60%且四线加快15%",
        {"demand_all": 2, "cap_mul": 1.6, "avail": faster(1.15)}, against=ref2)
    add("bundle", q, "需求×2且上限四线仓库一起上",
        {"demand_all": 2, "cap_mul": 1.6, "avail": faster(1.15), "fg_hold": 800}, against=ref2)
    add("bundle", q, "需求×2且上限+60%四线加快30%且仓库",
        {"demand_all": 2, "cap_mul": 1.6, "avail": faster(1.30), "fg_hold": 800}, against=ref2)
    q = "几件坏事同时发生时，要花多少钱、交得出多少台？"
    shock = {"demand_all": 1.4, "elec": 1.3, "wage": 1.12, "max_shifts": 2}
    shock_name = "订单多四成+电费涨三成+工资涨12%+不许夜班"
    add("stack", q, shock_name, shock)
    add("stack", q, "这套压力下改月度上限+15%", {**shock, "cap_mul": 1.15}, against=shock_name)
    add("stack", q, "这套压力下改用仓库", {**shock, "fg_hold": 800}, against=shock_name)
    add("stack", q, f"订单多四成且{peak}月四条线各停3天",
        {"demand_all": 1.4, "down": {f"ALL|{peak}": 3}})
    chip = models[1] if len(models) > 1 else models[0]
    add("stack", q, f"订单多三成且{chip}春天零件只够一半且涂装{peak}月停5天",
        {"demand_all": 1.3, "supply": {f"{chip}|{t}": 0.55 for t in (4, 5, 6)}, "down": {f"PNT|{peak}": 5}})
    add("stack", q, "订单减半且不许整天停线", {"demand_all": 0.5, "no_flex": True})
    add("stack", q, f"订单多六成且电费涨三成且涂装{peak}月停5天",
        {"demand_all": 1.6, "elec": 1.3, "down": {f"PNT|{peak}": 5}})
    # 假设登记表里 A01–A11。已经在淡季验过的，改到「建议真正会变」的产量上再验一次。
    q = "这些假设换到忙的时候，还会不会改变前面的建议？"
    staffed = "需求×1.6且月上限+25%"
    staff = {"demand_all": 1.6, "cap_mul": 1.25}
    add("hyp", q, "多六成且已改表，但每月人数最多加2%", staff, {"head_up": 0.02, "head_dn": 0.15}, against=staffed)
    add("hyp", q, "多六成且已改表，但完全不能再加人", staff, {"head_up": 0, "head_dn": 0.15}, against=staffed)
    add("hyp", q, "多六成且已改表，换档一次200万并损失10天",
        {**staff, "switch_cost": 2_000_000, "switch_days": 10}, against=staffed)
    add("hyp", q, "多六成且已改表，年初三个月效率只有75%",
        {**staff, "ramp": {f"ALL|{t}": 0.75 for t in (1, 2, 3)}}, against=staffed)
    add("hyp", q, "多六成且已改表，但不许车间借人", {**staff, "borrow": 0}, against=staffed)
    add("hyp", q, "多六成且已改表，临时工降到零", {**staff, "dispatch": 0}, against=staffed)
    add("hyp", q, "多六成且已改表，停工日发全薪", {**staff, "stop_pay": 1}, against=staffed)
    mix_name = f"{models[0]}全年+35%"
    add("hyp", q, f"{models[0]}多35%且全厂效率打九折",
        {"demand_model": {models[0]: 1.35}, "avail": {f"ALL|{t}": 0.9 for t in months}}, against=mix_name)
    add("hyp", q, f"计划维修放在{trough}月，四条线各停2天", {"down": {f"ALL|{trough}": 2}})
    add("hyp", q, f"计划维修放在{peak}月，四条线各停2天", {"down": {f"ALL|{peak}": 2}})
    add("hyp", q, "涂装周末改为完全停机", {"weekend_policy": {"PNT": "shutdown"}})
    add("hyp", q, "订单多四成且涂装周末完全停机",
        {"demand_all": 1.4, "weekend_policy": {"PNT": "shutdown"}}, against="需求×1.4")

def extreme_enabled(explicit=None):
    """推到极限开关。调用时写明的真假优先，其次命令行，最后看 data/switches.csv。默认关。"""
    if explicit is not None:
        return bool(explicit)
    if "--extreme" in sys.argv:
        return True
    if "--no-extreme" in sys.argv:
        return False
    path = os.path.join(H, "data", "switches.csv")
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("key") == "extreme":
                return str(r.get("value", "0")).strip().lower() in ("1", "true", "yes", "on", "开")
    return False

def _idx(plan):
    return {(r["shop"], r["month"]): r for r in plan}

SHIFT_NAME = {0: "不开线", 1: "只开白班", 2: "开两班", 3: "开三班"}

def _how(jph, shifts):
    name = SHIFT_NAME.get(int(round(shifts)), f"开{int(round(shifts))}班")
    return f"每小时 {int(round(jph))} 台、{name}"

def describe_changes(a, b, limit=4):
    """每个车间用一句话：从每小时多少台、开几班，改成什么样。"""
    A, B = _idx(a), _idx(b)
    by = {}
    for (s, t), y in B.items():
        x = A.get((s, t))
        if not x: continue
        if abs(y["jph"] - x["jph"]) < 0.1 and abs(y["shifts"] - x["shifts"]) < 0.1: continue
        key = (int(round(x["jph"])), int(round(x["shifts"])), int(round(y["jph"])), int(round(y["shifts"])))
        by.setdefault(s, {}).setdefault(key, 0)
        by[s][key] += 1
    parts = []
    for s, kinds in by.items():
        key, n = max(kinds.items(), key=lambda kv: kv[1])
        extra = sum(v for k, v in kinds.items() if k != key)
        bit = f"{SN.get(s, s)}有 {n} 个月从{_how(key[0], key[1])}改成{_how(key[2], key[3])}"
        if extra: bit += f"，另有 {extra} 个月是别的调法"
        parts.append(bit)
    return "；".join(parts[:limit])

def _money_bucket(name):
    """制造费里的科目归成人工、能源、车间。交不出的罚款单独拿出，不进制造费。"""
    if name.startswith("权重") or name in ("边际贡献", "−边际贡献"):
        return None
    if "缺口惩罚" in name:
        return "罚款"
    if any(s in name for s in ("人工", "加班", "夜班", "借调")):
        return "人工"
    if name.startswith("能源") or name in ("需量电费", "启停能耗") or "停工日能源" in name:
        return "能源"
    return "车间"

def money_split(before, after, op_delta):
    """人工、能源四舍五入到 0.1 万，车间用差额补齐，保证三者相加等于制造费差。"""
    raw = {"人工": 0.0, "能源": 0.0, "罚款": 0.0}
    for k in set(before) | set(after):
        bucket = _money_bucket(k)
        if bucket in raw:
            raw[bucket] += (after.get(k, 0) - before.get(k, 0)) / 1e4
    labor, energy = round(raw["人工"], 1), round(raw["能源"], 1)
    shop = round(float(op_delta) - labor - energy, 1)
    return dict(人工差_万元=labor, 能源差_万元=energy, 车间差_万元=shop, 罚款差_万元=round(raw["罚款"], 1))

def account_line(r):
    if not r or r.get("人工差_万元") in (None, ""):
        return ""
    labor, energy, shop, pen = (float(r[k]) for k in ("人工差_万元", "能源差_万元", "车间差_万元", "罚款差_万元"))
    op = float(r["较参照_万元"])
    who = r.get("参照") if r.get("参照") not in (None, "", "—") else "今年"
    plan = r.get("方案变化说明") or ""
    plan_bit = f"排班：{plan}。" if plan else "排班没有改。"
    return (f"对账（对照{who}）：制造费 {op:+,.1f} 万 = 人工 {labor:+,.1f} 万 + 能源 {energy:+,.1f} 万 + 车间和其他 {shop:+,.1f} 万。"
            f"交不出的罚款另计 {pen:+,.1f} 万，不在制造费里。{plan_bit}")

def aside(r, level, note):
    line = account_line(r)
    trust = f"可信程度：{level}。{note}"
    return ((" " + line) if line else "") + " " + trust

def other_sheet():
    path = os.path.join(H, "output", "v5", "管理层决策单.md")
    cost, bound = "44,297 万", "再多 28.5%"
    if os.path.exists(path):
        text = open(path, encoding="utf-8").read()
        import re
        m = re.search(r"\|\s*成本优先\s*\|\s*([0-9,]+)\s*\|", text)
        if m: cost = m.group(1) + " 万"
        m = re.search(r"全年需求上浮：\+([0-9.]+%)", text)
        if m: bound = "再多 " + m.group(1)
    return cost, bound


def prebuild(a, b):
    """本月少做至少 800 台、上月多做至少 800 台并且缓存升高 → 才算提前生产。
    全年重排里几十、一两百台的搬动不算。"""
    A, B = _idx(a), _idx(b); hits = []
    for (s, t), y in B.items():
        x, xp, yp = A.get((s, t)), A.get((s, t - 1)), B.get((s, t - 1))
        if not x or not xp or not yp: continue
        if x["volume"] - y["volume"] >= 800 and yp["volume"] - xp["volume"] >= 800 and yp["buffer_end"] > xp["buffer_end"] + 80:
            hits.append(f"{SN.get(s, s)}{t-1}月")
    return hits

def switches(plan):
    n = 0
    for s in {r["shop"] for r in plan}:
        rows = sorted((r for r in plan if r["shop"] == s), key=lambda r: r["month"])
        n += sum(abs(a["jph"] - b["jph"]) > 0.1 for a, b in zip(rows, rows[1:]))
    return n

def drivers(ca, cb):
    rows = []
    for k in set(ca) | set(cb):
        dv = (cb.get(k, 0) - ca.get(k, 0)) / 1e4
        if abs(dv) >= 0.5: rows.append((k, dv))
    rows.sort(key=lambda kv: -abs(kv[1]))
    return rows[:4]

def driver_text(rows):
    return "、".join(f"{k}{v:+.0f}万" for k, v in rows) or "科目变化不到 0.5 万"

def response_label(d):
    tags = []
    if d["升档月"]: tags.append("升档")
    if d["加开班月"]: tags.append("加开班")
    if d["降档月"]: tags.append("降档")
    if d["减班月"]: tags.append("减班")
    if d["加班差h"] > 80: tags.append("加班")
    elif d["加班差h"] < -80: tags.append("少加班")
    if d["停工日差"] > 1: tags.append("停工日")
    if d["预产"]: tags.append("提前生产")
    if d["流失差"] > 1 or d["延期差"] > 200: tags.append("延期或流失")
    if not tags: tags.append("方案不变")
    # 去重保持顺序
    out = []
    for t in tags:
        if t not in out: out.append(t)
    return "+".join(out)

def _count_dir(a, b, key, sign):
    A, B = _idx(a), _idx(b); n = 0
    for k, y in B.items():
        x = A.get(k)
        if not x: continue
        dv = y[key] - x[key]
        if sign > 0 and dv > 0.1: n += 1
        if sign < 0 and dv < -0.1: n += 1
    return n

def assess(ref, new):
    """对照 ref，给出这一情景相对参照的应对和一句话。ref/new 为 solve_case 的结果。"""
    if new.get("status") == "error" or not new.get("plan"):
        return dict(状态=new.get("status", "error"), 运营成本_万元="", 较参照_万元="", 单车_元="", 产量="",
                    流失="", 延期台月="", 加班h="", 三班月="", 停工日="", 借调人月="", 换档次数="",
                    方案变化=0, 应对="求解失败", 方案变化说明="", 成本驱动="", 判断=new.get("error", "求解失败"),
                    利用率="", 人工差_万元="", 能源差_万元="", 车间差_万元="", 罚款差_万元="",
                    升档月=0, 降档月=0, 加开班月=0, 减班月=0, 加班差h=0, 停工日差=0, 流失差=0, 延期差=0, 预产="")
    plan, cost, kp = new["plan"], new["cost"], new["kpi"]
    op = kp["运营成本"] / 1e4
    lost = kp["流失台"]; delay = kp["延期台月"]
    if ref is None or ref.get("status") == "error" or not ref.get("plan"):
        ref = new
    rp, rc, rk = ref["plan"], ref["cost"], ref["kpi"]
    info = dict(
        升档月=_count_dir(rp, plan, "jph", 1), 降档月=_count_dir(rp, plan, "jph", -1),
        加开班月=_count_dir(rp, plan, "shifts", 1), 减班月=_count_dir(rp, plan, "shifts", -1),
        加班差h=sum(r["ot_hours"] for r in plan) - sum(r["ot_hours"] for r in rp),
        停工日差=sum(r["stop_days"] for r in plan) - sum(r["stop_days"] for r in rp),
        流失差=lost - rk["流失台"], 延期差=delay - rk["延期台月"], 预产="、".join(prebuild(rp, plan)))
    structural = info["升档月"] + info["降档月"] + info["加开班月"] + info["减班月"]
    label = response_label(info)
    change = describe_changes(rp, plan)
    delta = round(op - rk["运营成本"] / 1e4, 1)
    split = money_split(rc, cost, delta)
    drv = (f"人工{split['人工差_万元']:+.0f}万、能源{split['能源差_万元']:+.0f}万、车间和其他{split['车间差_万元']:+.0f}万；"
           f"罚款另计{split['罚款差_万元']:+.0f}万，不在制造费里")
    same_delivery = abs(info["流失差"]) <= 1 and abs(info["延期差"]) <= 200
    if structural == 0 and same_delivery and abs(info["加班差h"]) <= 80 and info["停工日差"] <= 1 and not info["预产"]:
        judge = f"班次和每小时台数不动，交付也不动。制造费 {delta:+.0f} 万，其中{drv}。"
    else:
        delivery = "交付守住。" if same_delivery else f"交不出 {info['流失差']:+.0f} 台，晚交 {info['延期差']:+.0f} 个「一台晚一个月」。"
        where = f"排班：{change}。" if change else ""
        pre = f"提前生产：{info['预产']}。" if info["预产"] else ""
        judge = f"制造费 {delta:+.0f} 万，每台 {kp['单车成本']:.0f} 元。{delivery}{where}{pre}对账：{drv}。"
    if new.get("status") != "Optimal":
        judge = f"（状态 {new['status']}）" + judge
    util = []
    for s in dict.fromkeys(r["shop"] for r in plan):
        us = [r["util"] for r in plan if r["shop"] == s]
        util.append(f"{SN.get(s, s)}{sum(us)/len(us):.0%}")
    return dict(状态=new["status"], 运营成本_万元=round(op, 1), 较参照_万元=delta,
                单车_元=round(kp["单车成本"]), 产量=round(new["out"]), 流失=round(lost), 延期台月=round(delay),
                加班h=round(kp["加班h"]), 三班月=sum(r["shifts"] == 3 for r in plan),
                停工日=round(sum(r["stop_days"] for r in plan), 1),
                借调人月=round(sum(r["borrowed"] for r in plan), 1), 换档次数=switches(plan),
                方案变化=structural, 应对=label, 方案变化说明=change, 成本驱动=drv, 判断=judge,
                利用率="/".join(util), **split, **info)

def _job(item):
    d, name, kw = item
    try:
        return engine.solve_case(d, name, **kw)
    except Exception as e:
        return {"name": name, "status": "error", "error": f"{type(e).__name__}: {e}", "plan": [], "cost": {}, "kpi": {}}

def solve_all(base, cases, procs=4):
    jobs = []
    for c in cases:
        d = apply_knobs(base, c["knobs"]); d["g"]["solver_time_limit"] = TIME_LIMIT
        jobs.append((d, c["name"], dict(c["build"])))
    if procs <= 1:
        return [_job(j) for j in jobs]
    for d, _, _ in jobs:
        d["g"]["threads"] = 1
    with mp.get_context("spawn").Pool(min(procs, len(jobs))) as pool:
        return pool.map(_job, jobs)

def build_rows(cases, solved):
    by = {s["name"]: s for s in solved}
    rows = []
    for c, s in zip(cases, solved):
        ref_name = c["against"] or c["name"]
        ref = by.get(ref_name) if c["against"] else None
        a = assess(ref, s)
        rows.append(dict(问题编号=c["qid"], 问题=c["问题"], 场景=c["name"], 参照=c["against"] or "—",
                         轴=c["axis"], 水平=c["level"], **{k: v for k, v in a.items() if k not in ("升档月", "降档月", "加开班月", "减班月", "加班差h", "停工日差", "流失差", "延期差")}))
        rows[-1]["_d"] = a   # 解读用，写 CSV 前去掉
    return rows

def _num(rows, pred=None):
    out = []
    for r in rows:
        if r.get("状态") in ("error",) or r.get("运营成本_万元", 0) == "": continue
        if pred and not pred(r): continue
        out.append(r)
    return out

def read_demand(sub, _all):
    sub = sorted(_num(sub), key=lambda r: float(r["水平"]))
    if not sub: return "需求轴没有解出来。"
    lo = [r for r in sub if float(r["水平"]) < 1]; hi = [r for r in sub if float(r["水平"]) > 1]
    bits = []
    if lo:
        r = min(lo, key=lambda r: float(r["水平"]))
        bits.append(f"降到 ×{float(r['水平']):g} 时单车 {r['单车_元']} 元（固定成本摊薄变差），应对是{r['应对']}")
    changed = [r for r in hi if r["方案变化"]]
    held = [r for r in hi if not r["方案变化"] and r["流失"] < 1]
    if held and not changed:
        bits.append("扫过的增产都没改班次和 JPH，交付也守住，余量还在")
    elif changed:
        r = changed[0]
        bits.append(f"增产从 ×{float(r['水平']):g} 开始改方案（{r['方案变化说明'] or r['应对']}）")
    lost = [r for r in hi if r["流失"] >= 100]
    delay = [r for r in hi if r["延期台月"] >= 200]
    if lost:
        r = lost[0]
        bits.append(f"×{float(r['水平']):g} 起出现流失 {r['流失']} 台，再往上不能只靠排产承诺交付")
    elif delay:
        r = delay[0]
        bits.append(f"×{float(r['水平']):g} 起延期 {r['延期台月']} 台·月，但年内还能补上（流失 {r['流失']}）")
    else:
        top = hi[-1] if hi else sub[-1]
        bits.append(f"放到 ×{float(top['水平']):g} 仍无流失，交付边界高于这次扫描")
    return "。".join(bits) + "。"

def read_down(sub, _all):
    sub = _num(sub)
    five = [r for r in sub if str(r["水平"]) in SN or r["轴"] == "停线5天"]
    five = sorted(five, key=lambda r: -abs(float(r["较参照_万元"])))
    if not five: return "停线情景没有解出来。"
    order = sorted(five, key=lambda r: -float(r["较参照_万元"]))
    bits = ["高峰月各停 5 天，按运营成本：" + "；".join(f"{r['场景']} {float(r['较参照_万元']):+.0f} 万（{r['应对']}）" for r in order)]
    for r in five:
        if r["流失"] >= 1 or r["延期台月"] >= 50:
            bits.append(f"{r['场景']}没有完全吸收：流失 {r['流失']}、延期 {r['延期台月']} 台·月")
    return "。".join(bits) + "。"

def read_factor(sub, _all):
    sub = _num(sub)
    ident = [r for r in sub if str(r["场景"]).startswith("涂装全年")]
    bits = []
    if len(ident) >= 2:
        costs = [float(r["较参照_万元"]) for r in ident]
        plans = [r["方案变化"] for r in ident]
        if max(costs) - min(costs) <= 1 and len(set(plans)) == 1:
            bits.append("涂装全年打到 0.85 时，开动率、OEE、FTT、出勤四条的成本和方案一致：基础口径里它们只是同一个产能折扣，分不出质量损失和设备损失。FTT 也不能按月单独设")
        else:
            detail = "；".join(f"{r['场景']} {float(r['较参照_万元']):+.0f} 万/{r['应对']}" for r in ident)
            bits.append("四条折扣并不等价：" + detail)
    rest = [r for r in sub if r not in ident]
    for r in rest:
        bits.append(f"{r['场景']}：{str(r['判断']).rstrip('。')}")
    return "。".join(bits) + ("。" if bits else "")

def read_price(sub, _all):
    sub = _num(sub)
    if not sub: return "价格情景没有解出来。"
    still = [r for r in sub if r["方案变化"] == 0]
    moved = [r for r in sub if r["方案变化"]]
    bits = []
    if still:
        bits.append("不改排产的有：" + "；".join(f"{r['场景']} {float(r['较参照_万元']):+.0f} 万" for r in still))
    if moved:
        bits.append("会改班次或 JPH 的有：" + "；".join(f"{r['场景']}（{r['方案变化说明'] or r['应对']}，{float(r['较参照_万元']):+.0f} 万）" for r in moved))
    if still and not moved:
        bits.append("这些单价冲击只传导成本，不能当成要改班次的信号")
    return "。".join(bits) + "。"

def read_policy(sub, _all):
    sub = _num(sub)
    if not sub: return "政策情景没有解出来。"
    direct = [r for r in sub if r["参照"] in ("基准", "—", "")]
    paired = [r for r in sub if r not in direct]
    bits = []
    held = [r for r in direct if r["流失"] < 1 and r["延期台月"] < 50]
    broken = [r for r in direct if r not in held]
    if held:
        held = sorted(held, key=lambda r: float(r["较参照_万元"]))
        bits.append("相对基准、交付还能守住时，约束从便宜到贵：" + "；".join(f"{r['场景']} {float(r['较参照_万元']):+.0f} 万" for r in held))
    if broken:
        bits.append("交付被碰到的约束：" + "；".join(f"{r['场景']} 流失 {r['流失']}、延期 {r['延期台月']} 台·月，成本 {float(r['较参照_万元']):+.0f} 万" for r in broken))
    by_ref = {}
    for r in paired: by_ref.setdefault(r["参照"], []).append(r)
    for ref, rs in by_ref.items():
        rs = sorted(rs, key=lambda r: float(r["较参照_万元"]))
        bits.append("相对" + ref + "：" + "；".join(
            f"{r['场景']} {float(r['较参照_万元']):+.0f} 万、流失 {r['流失']}、延期 {r['延期台月']} 台·月" for r in rs))
    return "。".join(bits) + "。"

def read_assume(sub, _all):
    sub = _num(sub)
    if not sub: return "假设情景没有解出来。"
    quiet, loud = [], []
    for r in sub:
        if r["方案变化"] == 0 and abs(float(r["较参照_万元"])) < 5:
            quiet.append(r["场景"])
        else:
            loud.append(f"{r['场景']}（{r['应对']}，{float(r['较参照_万元']):+.0f} 万，{r['方案变化说明'] or '方案结构未改'}）")
    bits = []
    if quiet:
        bits.append("相对同一低需求，下面这些假设不改变方案、成本差也小于 5 万：" + "、".join(quiet))
    if loud:
        bits.append("会改变做法或成本的是：" + "；".join(loud))
    if quiet and not loud:
        bits.append("低负荷下先别为派遣比、停工发薪、换档成本争论排产，它们还没敏感")
    return "。".join(bits) + "。"

def read_penalty(sub, allrows):
    sub = _num(sub)
    base = {r["场景"]: r for r in _num(allrows)}
    if "需求×1.4" in base and all(r["场景"] != "需求×1.4" for r in sub):
        sub = sub + [base["需求×1.4"]]
    if not sub: return "惩罚情景没有解出来。"
    bits = []
    for label, keys in (("×1.25", [r for r in sub if "1.25" in str(r["场景"])]),
                        ("×1.4", [r for r in sub if "1.4" in str(r["场景"])])):
        if not keys: continue
        lost = {r["流失"] for r in keys}; cost = {float(r["运营成本_万元"]) for r in keys}
        if len(lost) == 1 and len(cost) == 1:
            n = next(iter(lost))
            if n < 1:
                bits.append(f"需求{label}把丢单惩罚从 0.3 万调到 20 万，流失仍是 0，运营成本也不变。这个需求交得完，惩罚高低不影响排产")
            else:
                bits.append(f"需求{label}把惩罚从 0.3 万调到 20 万，流失始终是 {n} 台、成本也不变。这些台是产能顶住的，提高惩罚买不回来")
        else:
            few = min(keys, key=lambda r: (r["流失"], -float(r["运营成本_万元"])))
            many = max(keys, key=lambda r: (r["流失"], -float(r["运营成本_万元"])))
            bits.append(
                f"需求{label}：流失最少的是{few['场景']}（{few['流失']} 台，运营成本 {few['运营成本_万元']} 万），"
                f"最多的是{many['场景']}（{many['流失']} 台，{many['运营成本_万元']} 万），只差 {many['流失'] - few['流失']} 台。"
                f"把惩罚抬高买不回大部分缺口，那些台是产能顶住的")
    return "。".join(bits) + "。"

def read_neck(sub, allrows):
    sub = _num(sub)
    ref = next((r for r in allrows if r["场景"] == "需求×1.4"), None)
    if not sub or not ref: return "瓶颈情景没有解出来。"
    base_lost = ref["流失"]
    rows = sorted(sub, key=lambda r: (r["流失"], float(r["较参照_万元"])))
    bits = []
    for r in rows:
        bits.append(f"{r['场景']}流失 {r['流失']} 台（比 ×1.4 少 {base_lost - r['流失']}），运营成本 {float(r['较参照_万元']):+.0f} 万")
    jph = [r for r in rows if "车间产能" in r["场景"] or r["场景"].endswith("产能+15%")]
    cap = [r for r in rows if "月上限" in r["场景"]]
    if jph and all(base_lost - r["流失"] < 50 for r in jph):
        cheap = min(jph, key=lambda r: float(r["较参照_万元"]))
        bits.append(f"节拍加 15% 一台都找不回。成本下降最多的是{cheap['场景']}（{float(cheap['较参照_万元']):+.0f} 万），只是同样的产量少开了班。流失卡在车型月度上限，不在 JPH")
    if cap:
        r = cap[0]
        bits.append(f"放宽车型月上限 15% 后流失 {r['流失']} 台，找回 {base_lost - r['流失']} 台")
    fg = [r for r in rows if "成品库" in r["场景"]]
    if fg:
        r = fg[0]
        bits.append(f"启用成品库（持有 800 元/台·月）后流失 {r['流失']} 台，找回 {base_lost - r['流失']} 台，运营成本 {float(r['较参照_万元']):+.0f} 万")
    return "。".join(bits) + "。"

def read_list(sub, _all):
    sub = _num(sub)
    if not sub: return "没有解出来。"
    return "；".join(f"{r['场景']}：{str(r['判断']).rstrip('。')}" for r in sub)

def _delivered(r, limit=100):
    return int(float(r["流失"])) < limit

def read_bundle(sub, allrows):
    """同一参照下，交得出的办法里挑最便宜的，交不出的单独点名。"""
    sub = _num(sub)
    if not sub: return "组合办法没有解出来。"
    by = {}
    for r in sub: by.setdefault(r["参照"], []).append(r)
    bits = []
    for ref, rs in by.items():
        base = next((r for r in allrows if r["场景"] == ref), None)
        rs = sorted(rs, key=lambda r: (int(float(r["流失"])), float(r["运营成本_万元"])))
        head = f"对照{ref}"
        if base and base.get("流失") != "":
            head += f"（什么都不做会交不出 {base['流失']} 台）"
        ok = [r for r in rs if _delivered(r)]
        bad = [r for r in rs if not _delivered(r)]
        parts = []
        if ok:
            best = min(ok, key=lambda r: float(r["运营成本_万元"]))
            parts.append(
                f"能把交不出压到 100 台以内、又最省钱的是「{best['场景']}」，仍交不出 {best['流失']} 台，"
                f"制造费比对照 {float(best['较参照_万元']):+.0f} 万")
        if bad:
            parts.append("交不出仍超过 100 台的有：" + "；".join(
                f"{r['场景']}还剩 {r['流失']} 台、制造费 {float(r['较参照_万元']):+.0f} 万" for r in bad))
        bits.append(head + "：" + "。".join(parts))
    return "。".join(bits) + "。"

def _moved(r, ref):
    lost = int(float(r["流失"])) - (int(float(ref["流失"])) if ref else 0)
    delay = int(float(r["延期台月"])) - (int(float(ref["延期台月"])) if ref else 0)
    return lost, delay, float(r["较参照_万元"])

def read_hyp(sub, allrows):
    sub = _num(sub)
    if not sub: return "假设情景没有解出来。"
    idx = {r["场景"]: r for r in allrows}
    bits = []
    for r in sub:
        ref = idx.get(r["参照"]) if r["参照"] not in ("基准", "—", "") else idx.get("基准")
        lost, delay, cost = _moved(r, ref)
        if abs(lost) < 100 and abs(delay) < 500 and abs(cost) < 100:
            bits.append(f"{r['场景']}：不改变建议（交不出 {lost:+} 台，晚交 {delay:+}，制造费 {cost:+.0f} 万）")
        else:
            bits.append(f"{r['场景']}：要改建议（交不出 {lost:+} 台，晚交 {delay:+}，制造费 {cost:+.0f} 万，应对 {r['应对']}）")
    return "；".join(bits) + "。"

def read_stack(sub, _all):
    sub = _num(sub)
    if not sub: return "叠加情景没有解出来。"
    bits = []
    for r in sub:
        where = "比今年" if r["参照"] in ("基准", "—", "") else f"相对{r['参照']}"
        bits.append(f"{r['场景']}：交不出 {r['流失']} 台，晚交 {r['延期台月']}，制造费{where} {float(r['较参照_万元']):+.0f} 万")
    return "；".join(bits) + "。"

READERS = {
    "demand": read_demand, "down": read_down, "factor": read_factor, "price": read_price,
    "policy": read_policy, "assume": read_assume, "penalty": read_penalty,
    "shape": read_list, "mix": read_list, "supply": read_list, "library": read_list, "combo": read_list,
    "neck": read_neck, "bundle": read_bundle, "stack": read_stack, "hyp": read_hyp,
}

def findings(rows):
    order, seen = [], set()
    for r in rows:
        if r["问题编号"] in ("ref",) or r["问题编号"] in seen: continue
        seen.add(r["问题编号"]); order.append(r["问题编号"])
    out = []
    for qid in order:
        sub = [r for r in rows if r["问题编号"] == qid]
        fn = READERS.get(qid, read_list)
        out.append(dict(问题编号=qid, 问题=sub[0]["问题"], 结论=fn(sub, rows)))
    return out

def _public(row):
    return {k: v for k, v in row.items() if not k.startswith("_")}

def _by(rows):
    return {r["场景"]: r for r in rows if r.get("运营成本_万元") != ""}

def _wan(v, sign=False):
    x = float(v)
    return f"{x:+,.0f}" if sign else f"{x:,.0f}"

def _line(cells):
    return "| " + " | ".join(str(c) for c in cells) + " |"

def _has(r):
    return r is not None and r.get("运营成本_万元") != ""

def _lost_n(r):
    return int(float(r["流失"]))

def _gap(a, c):
    """a 比 c 多出来的制造费（万元）。"""
    return float(a["运营成本_万元"]) - float(c["运营成本_万元"])

def limit_notes(b):
    """极限和组合办法的建议句。交车和省钱分开说，避免把「少开班」说成「才能交上」。"""
    adv = []
    base, d14 = b.get("基准"), b.get("需求×1.4")
    caps = []
    for pct, name in ((5, "需求×1.4且月上限+5%"), (8, "需求×1.4且月上限+8%"),
                      (10, "需求×1.4且月上限+10%"), (15, "需求×1.4且车型月上限+15%")):
        r = b.get(name)
        if _has(r): caps.append((pct, r))
    if caps and _has(d14):
        clear = [(p, r) for p, r in caps if _lost_n(r) < 100]
        stuck = [(p, r) for p, r in caps if _lost_n(r) >= 100]
        if clear and stuck:
            p, r = min(clear)
            sp, sr = max(stuck)
            same = [q for q, rr in clear if abs(float(rr["运营成本_万元"]) - float(r["运营成本_万元"])) < 1]
            extra = ""
            if len(same) > 1:
                extra = f"再放到 {max(same)}%，制造费还是这么多，多放宽的额度用不上。"
            adv.append(
                f"**订单多四成时，月度上限放到 {p}% 就够，不用一下子放宽 15%。** 放宽 {sp}% 还交不出 {_lost_n(sr)} 台。"
                f"放到 {p}% 可以全部交上，制造费比硬扛多 {_wan(r['较参照_万元'])} 万。{extra}"
                + aside(r, "可拿来讨论方向", "放到刚好能交完即可。再放宽如果制造费不变，多出来的额度用不上。"))
    holds = []
    for label, name in (("200 元", "需求×1.4且仓库200元"), ("800 元", "需求×1.4且成品库800元"),
                        ("2,000 元", "需求×1.4且仓库2000元")):
        r = b.get(name)
        if _has(r): holds.append((label, r))
    if len(holds) >= 2 and all(_lost_n(r) < 100 for _, r in holds):
        cheap, dear = holds[0], holds[-1]
        adv.append(
            f"**改不了月度上限时，仓库越贵，多花的钱就越多，但车都交得上。** "
            + "、".join(f"每台每月 {lb}要多花 {_wan(r['较参照_万元'])} 万" for lb, r in holds)
            + f"。最贵档比最便宜档多 {_wan(_gap(dear[1], cheap[1]))} 万，大体是按仓库租金走的。"
            f"能改表的话，改表只要约 {_wan(caps[1][1]['较参照_万元']) if len(caps) > 1 else '一百多'} 万，仍然更便宜。"
            + aside(holds[1][1] if len(holds) > 1 else holds[0][1], "可拿来讨论方向", "仓库单价是假设。租金越高，多花的钱越多，但不要把它理解成交不出的罚款。"))
    night, cap15 = b.get("需求×1.4且上限+15%但不许夜班"), b.get("需求×1.4且车型月上限+15%")
    if _has(night) and _has(cap15):
        extra = _gap(night, cap15)
        if _lost_n(night) < 100:
            late = f"不过会晚交 {night['延期台月']} 个「一台晚一个月」。" if int(float(night["延期台月"])) >= 200 else "晚交也可以忽略。"
            adv.append(
                f"**订单多四成时，不许开夜班也不会把「放宽月度上限」堵死。** 上限放宽 15% 之后车仍能在年底交完。{late}"
                f"比「可以开夜班」多花 {_wan(extra)} 万。"
                + aside(night, "可拿来讨论方向", "不许夜班之后仍可能晚交。晚交记在延期里，不等于年底交不出。"))
        else:
            adv.append(
                f"**不许开夜班之后，只放宽月度上限就不够了。** 还剩 {_lost_n(night)} 台交不出。要改用仓库，或者允许夜班。")
    d16 = b.get("需求×1.6")
    c16, s16, w16 = b.get("需求×1.6且月上限+25%"), b.get("需求×1.6且四线加快15%"), b.get("需求×1.6且仓库800元")
    both, nonight = b.get("需求×1.6且上限+25%且四线加快15%"), b.get("需求×1.6且上限+25%但不许夜班")
    if all(_has(r) for r in (d16, c16, s16, w16, both)):
        saved = _gap(c16, both)
        adv.append(
            f"**订单多六成时，只做一件事就够：月度上限放宽约 25%。** 什么都不做会交不出 {_lost_n(d16)} 台；只改表可以全部交上，"
            f"制造费比今年多 {_wan(_gap(c16, base)) if _has(base) else c16['较参照_万元']} 万，每台 {_wan(c16['单车_元'])} 元。"
            f"只把生产线加快 15%，交不出的还是 {_lost_n(s16)} 台。只放仓库只能把交不出的减少 {_lost_n(d16) - _lost_n(w16)} 台，还剩 {_lost_n(w16)} 台，"
            f"因为每个月的上限把车卡住了，淡季也做不出可以先存着的量。"
            f"改完表再把线加快 15%，交的车一样多，制造费能再少约 {_wan(saved)} 万。那是少开班省下来的，不是为了多交车。"
            + aside(c16, "可拿来讨论方向", "只改表就能交上。再加快生产线少下来的钱，是少开班，不能理解成多交了车。人能不能当月招齐，模型还算不准，见后面用人那条。"))
        if _has(nonight) and _lost_n(nonight) >= 100:
            adv.append(
                f"**订单多六成、同时又不许开夜班，只改月度上限就不够。** 上限放宽 25% 仍有 {_lost_n(nonight)} 台交不出。"
                f"要么允许夜班，要么在改表之外再把生产线加快。"
                + aside(nonight, "可拿来讨论方向", "订单多六成时，不许夜班会把只改表这条路堵死。和订单只多四成时不一样。"))
    d2, c2, f2 = b.get("需求×2"), b.get("需求×2且月上限+60%"), b.get("需求×2且上限+60%且四线加快15%")
    if all(_has(r) for r in (d2, c2, f2)) and _has(base):
        adv.append(
            f"**订单翻倍时，只把月度上限放宽 60%，年底也能交完。** 什么都不做会交不出 {_lost_n(d2)} 台。"
            f"只改表仍有晚交 {c2['延期台月']} 个「一台晚一个月」，制造费比今年多 {_wan(_gap(c2, base))} 万，每台 {_wan(c2['单车_元'])} 元。"
            f"再把生产线加快 15%，晚交可以消掉，制造费比「只改表」少 {_wan(_gap(c2, f2))} 万，每台降到 {_wan(f2['单车_元'])} 元。"
            f"上限已经放开以后，再加仓库没有额外作用。加快生产线是为了少花钱、少晚交，不是交车的前提。"
            + aside(c2, "可拿来讨论方向", "只改表能在年底交完，但还会晚交。加快生产线消掉的是晚交和费用，不是凭空多出来的交车能力。"))
    shock, fix, wh = (b.get("订单多四成+电费涨三成+工资涨12%+不许夜班"),
                      b.get("这套压力下改月度上限+15%"), b.get("这套压力下改用仓库"))
    if all(_has(r) for r in (shock, d14, fix)) and _has(base):
        adv.append(
            f"**电费涨三成、工资涨 12%、又不许夜班，叠在订单多四成上，交不出的还是 {_lost_n(shock)} 台，没有变得更多。** "
            f"多出来的是钱和晚交：制造费比「只是订单多四成」再多 {_wan(_gap(shock, d14))} 万。"
            f"这时仍先改月度上限，放宽 15% 后年底能交完，但还有晚交 {fix['延期台月']}。"
            + (f"改用仓库可以把晚交也消掉，制造费比改表再多 {_wan(_gap(wh, fix))} 万。" if _has(wh) else "")
            + aside(shock, "可拿来讨论方向", "这几件叠在一起，交不出的台数没有比只是订单多四成更多。多的是费用和晚交。"))
    piled = next((r for name, r in b.items() if "零件只够一半" in name and _has(r)), None)
    d13 = b.get("需求×1.3")
    if _has(piled) and _has(d13):
        adv.append(
            f"**订单只多三成时本来几乎能交完（交不出 {d13['流失']} 台）。再赶上一种车春天零件只够一半、涂装在最忙的月停 5 天，就会有 {_lost_n(piled)} 台到年底交不出。** "
            f"这三件事要放在一起看，不能用「每一件单独还能扛」来判断。"
            + aside(piled, "可拿来讨论方向", "单独看每一件时几乎都能交完。叠在一起才出现交不出，所以不能把单条结论摘出去用。"))
    half, half_stop = b.get("需求×0.5"), b.get("订单减半且不许整天停线")
    if _has(half) and _has(half_stop) and _has(base):
        adv.append(
            f"**订单少掉一半时，车仍能交上，但每台制造费升到 {_wan(half['单车_元'])} 元**（今年是 {_wan(base['单车_元'])} 元）。"
            f"这时还不许整天停线，只再多花 {_wan(_gap(half_stop, half))} 万，比「订单少一成半却不许停线」轻得多。"
            + aside(half, "可拿来讨论方向", "订单少一半时每台变贵，是因为人工和车间开支摊到更少的车上。"))
    return adv

def hyp_notes(rows, b):
    """假设实验：交不出变动 ≥100 台、晚交 ≥500，或制造费 ≥100 万，才写进建议。"""
    hyps = [r for r in rows if r.get("问题编号") == "hyp" and _has(r)]
    if not hyps:
        return []
    adv, quiet = [], []
    def ref_of(r):
        if r["参照"] in ("基准", "—", ""):
            return b.get("基准")
        return b.get(r["参照"])
    by_name = {r["场景"]: r for r in hyps}
    handled = set()
    for r in hyps:
        lost, delay, cost = _moved(r, ref_of(r))
        r["_flip"] = (lost, delay, cost)
    hire2, hire0 = by_name.get("多六成且已改表，但每月人数最多加2%"), by_name.get("多六成且已改表，但完全不能再加人")
    if _has(hire2) and _has(hire0):
        handled.update((hire2["场景"], hire0["场景"]))
        cost = hire2["_flip"][2]
        adv.append(
            f"**『人要提前几个月才能到岗』这件事，现在的计算还说明不了。** 订单多六成、表也改了，规定每月人数最多加 2%，和规定之后完全不能加人，结果一样：年底都能交完，都只多花 {_wan(cost)} 万。"
            f"原因是一月份可以一次把人招满，后面不再加人。真正要招人培训一到三个月的限制还没放进模型，所以『只改表就够』在用人上偏乐观。"
            + aside(hire2, "模型算不出", "两条用人限制结果一样，不能当成已经核实「人可以当月招齐」。招人培训周期还没有放进模型。"))
    learn = by_name.get("多六成且已改表，年初三个月效率只有75%")
    if learn and abs(learn["_flip"][2]) >= 100:
        handled.add(learn["场景"])
        lost, delay, cost = learn["_flip"]
        adv.append(
            f"**新人或新班组如果年初三个月只有平时 75% 的效率，订单多六成时年底仍能交完，但制造费要多 {_wan(cost)} 万，晚交多 {delay} 个「一台晚一个月」。** "
            f"招人和培训要算进前三个月的产量，不能假设一月份就满产。"
            + aside(learn, "假设还没确认", "75% 是用来试方向的效率，不是实测的学习曲线。"))
    borrow = by_name.get("多六成且已改表，但不许车间借人")
    if borrow and (abs(borrow["_flip"][1]) >= 500 or abs(borrow["_flip"][2]) >= 100):
        handled.add(borrow["场景"])
        lost, delay, cost = borrow["_flip"]
        adv.append(
            f"**订单多六成、表已经改了，再不许车间之间借人：年底仍能交完，但晚交多 {delay}，制造费多 {_wan(cost)} 万。** "
            f"忙的时候借人假不假，仍然会影响交期和费用。"
            + aside(borrow, "假设还没确认", "借人只按一个月的人天平衡，没有核对是不是同一天刚好有空的人。省下或少花的钱偏乐观，不要单独拿去考核车间。"))
    mix = next((r for r in hyps if "效率打九折" in r["场景"]), None)
    if mix and abs(mix["_flip"][2]) >= 100:
        handled.add(mix["场景"])
        lost, delay, cost = mix["_flip"]
        adv.append(
            f"**一种车多出三成五，如果因此全厂变慢一成：年底交不出的台数没有再增加，制造费要再多 {_wan(cost)} 万。** "
            f"贵在要多开班，不是多丢车。车型结构一变，先问生产线会不会变慢。"
            + aside(mix, "假设还没确认", "全厂变慢一成是假设，不是已经测到的节拍损失。设备变慢、人没来齐、一次没做对，在这个计算里仍然是同一笔产能。"))
    trough = next((r for r in hyps if r["场景"].startswith("计划维修放在") and "2月" in r["场景"]), None)
    peak = next((r for r in hyps if r["场景"].startswith("计划维修放在") and "10月" in r["场景"]), None)
    if _has(trough) and _has(peak):
        handled.update((trough["场景"], peak["场景"]))
        gap = float(peak["较参照_万元"]) - float(trough["较参照_万元"])
        adv.append(
            f"**四条线各停 2 天做计划维修，放在 10 月比放在 2 月贵 {_wan(gap)} 万。** "
            f"2 月多花 {_wan(trough['较参照_万元'])} 万，10 月多花 {_wan(peak['较参照_万元'])} 万。差别不大，维修能改期就放在淡月，不必为此大改日历。"
            + aside(peak, "可拿来讨论方向", "差别只有几十万。能改期就放淡月，不必为此重排全年维修。"))
    for r in hyps:
        if r["场景"] in handled:
            continue
        lost, delay, cost = r["_flip"]
        if abs(lost) < 100 and abs(delay) < 500 and abs(cost) < 100:
            quiet.append(f"{r['场景']}（制造费 {cost:+.0f} 万）")
    if quiet:
        adv.append("**下面这些假设换到忙季再算一遍，建议不用改：** " + "；".join(quiet) + "。可信程度：这次不改变建议。换档很贵、临时工降到零、停工发全薪、涂装周末停机，在忙季、表已经改过的情况下，制造费几乎不动。")
    return adv

def write_brief(rows):
    """给没有产线背景的人看的建议。数字来自本次求解。"""
    b = _by(rows)
    def row(name): return b.get(name)
    base = row("基准")
    if not base:
        return "基准情景没有解出，简报无法生成。\n"
    d14, cap, jph = row("需求×1.4"), row("需求×1.4且车型月上限+15%"), row("需求×1.4且四车间产能+15%")
    fg = row("需求×1.4且成品库800元")
    p0, p12 = row("禁止三班"), row("需求×1.2且禁止三班")
    idle = row("需求×1.2且正常班利用率≤85%")
    stop, disp = row("需求×0.85且关闭停工日"), row("需求×0.85且派遣0%")
    wage, elec, gas = row("工资+12%"), row("电价+30%"), row("气价+50%")
    chip, combo = row("V451在4-6月供应55%"), row("组合冲击")
    on = any(r.get("问题编号") in ("bundle", "stack", "hyp") for r in rows)
    mode = ("本次打开了「推到极限」：订单从减半算到翻倍，并比较几套办法叠在一起、几件坏事同时发生、忙季假设还站不站得住。"
            if on else
            "本次没开「推到极限」，只算了常规情景。要看订单翻倍、办法组合和假设冲击，把 data/switches.csv 里的 extreme 改成 1，或运行时加上 --extreme。")
    sheet_cost, sheet_bound = other_sheet()
    parts = ["# 给工厂的建议", "",
             "> 下面的钱和台数来自示例数据上的计算，不是这家工厂的真实账单。制造费指人工、电费和车间开支，不含买零件的钱，也不含交不出的罚款。", "",
             mode, "",
             f"按今年这套计划，一年做 **{_wan(base['产量'])} 台**，制造费 **{_wan(base['运营成本_万元'])} 万元**，每台摊 **{_wan(base['单车_元'])} 元**，订单都能交上。全年几乎不用开夜班。", "",
             "## 这次用的口径", "",
             f"- 制造费用的是这一次求解：误差 0.01%，每题最多 60 秒。今年就是上面的 **{_wan(base['运营成本_万元'])} 万元**。",
             f"- 另一份 output/v5/管理层决策单.md 里，成本优先是 {sheet_cost}。那次把误差放到 0.2%、大约 40 秒。两份不要对到个位。",
             f"- 交不出不到 100 台，本页当成还能交完。决策单从交不出 1 台，或某个月积压超过 1,000 台，就算过不了，所以它写全年订单最多{sheet_bound}。开会以本页的 100 台为准。",
             "- 每条建议下面有对账：人工、能源、车间和其他，加起来等于制造费。罚款另列，不在制造费里。",
             "",
             "## 建议", "",
             "每一条都是：遇到这件事，建议这样做。后面跟着对账和可信程度。", ""]
    if d14 and cap and jph:
        parts.append(f"1. **订单要比今年多出三成以上时，先改「每种车每个月最多做多少台」这张表，不要先把生产线加快。** 订单多到今年的 1.4 倍，年底有 {d14['流失']} 台交不出去。四条线都加快 15%，交不出的还是 {jph['流失']} 台。把月度上限放宽 15%，这 {d14['流失']} 台全能交上，全年多花 {_wan(cap['较参照_万元'])} 万，大约每台 {float(cap['较参照_万元']) * 10000 / max(int(d14['流失']), 1):,.0f} 元。"
            + aside(cap, "可拿来讨论方向", "月度上限如果是模具、客户订单或发运码头的硬限制，这条就不成立，改看放仓库。模型里把线加快，只是产能乘一个数，分不清是设备变慢、人没来齐，还是一次没做对。")
            + " 加快生产线、车并没有多交上：" + account_line(jph))
    if fg and d14:
        parts.append(f"2. **如果那张月度上限是真限制、改不了（模具、客户订单或发运码头），就在淡季提前把车造好放进仓库。** 这样年底也能全部交上，但要多花 {_wan(fg['较参照_万元'])} 万，大约每台 {float(fg['较参照_万元']) * 10000 / max(int(d14['流失']), 1):,.0f} 元，上限只是计划表里的数字时，改表更便宜。"
            + aside(fg, "可拿来讨论方向", "这里的仓库费按每台每月 800 元假设，不是这家工厂的仓储合同。"))
    if p0 and p12 and idle:
        parts.append(f"3. **「不许开夜班」今年可以答应，订单多了再答应就要花钱。** 按今年的量，这条规矩只多花 {_wan(p0['较参照_万元'])} 万，因为本来也几乎不开夜班。订单比今年多两成时，要多花 {_wan(p12['较参照_万元'])} 万，车仍能交上。「线必须空出 15% 不要排满」不建议当常规：订单多两成时要多花 {_wan(idle['较参照_万元'])} 万。"
            + aside(p12, "可拿来讨论方向", "今年几乎不开夜班，所以今年看起来很便宜。要看的是订单多了以后。")
            + " 留出 15% 空档：" + account_line(idle))
    if stop and disp:
        parts.append(f"4. **淡季订单少一成半时，先问能不能整天停线，不要先争临时工比例。** 不允许整天停、每天都得开着，会多花 {_wan(stop['较参照_万元'])} 万。临时工从两成降到零，只多花 {_wan(disp['较参照_万元'])} 万，排班不用改。"
            + aside(stop, "假设还没确认", "能不能整天停、临时工占两成，都来自假设登记表，人事还没确认。临时工那条排班不变，先不要为这个比例争论。"))
    if wage and elec:
        parts.append(f"5. **工资上涨，排班不用改，把钱加进预算。电费大涨，要重新排班。** 工资涨 12%，制造费多 {_wan(wage['较参照_万元'])} 万。电费涨 30%，制造费多 {_wan(elec['较参照_万元'])} 万。"
            + (f"天然气涨一半，多花 {_wan(gas['较参照_万元'])} 万。" if gas else "")
            + " 工资：" + account_line(wage) + " 电费：" + account_line(elec)
            + " 可信程度：可拿来讨论方向。单价是示例。工资这条排班不动，电费这条排班会改，以对账里写的排班为准。")
    if chip and combo:
        parts.append(f"6. **只有一种车在春天缺零件，订单丢不了，但会晚交，要提前告诉客户。** 这种车 4 到 6 月零件只够一半时，年底仍能交完，晚交累计 { _wan(chip['延期台月']) } 个「一台晚一个月」，制造费多 {_wan(chip['较参照_万元'])} 万。旺季冲量、缺零件、限电三件一起发生时，会有 {combo['流失']} 台到年底交不出。"
            + aside(chip, "可拿来讨论方向", "零件只够一半是假设的供应缺口。几件事叠在一起的结论不能拆开，用单件事还能扛去代替。")
            + " 三件一起：" + account_line(combo))
    ga, stp = row("总装10月停5天"), row("冲压10月停5天")
    if ga and stp:
        parts.append(f"7. **10 月最忙时要停线检修，先保最后一道总装，最前面的冲压可以停。** 总装停 5 天多花 {_wan(ga['较参照_万元'])} 万，冲压停 5 天只多花 {_wan(stp['较参照_万元'])} 万。这两种情况车都还能补上。"
            + aside(ga, "可拿来讨论方向", "比的是同一个月、同样停 5 天。总装在最后，前面停了还有机会补，所以总装更贵。")
            + " 冲压：" + account_line(stp))
    n = 8
    for sentence in limit_notes(b) + hyp_notes(rows, b):
        parts.append(f"{n}. {sentence}")
        n += 1
    parts += ["", "## 订单多了以后，有多少台交不出", "",
              "「交不出」指到年底还交不了客户的台数。「晚交」指一台车晚一个月，累加起来的数量。", "",
              _line(["订单是今年的几倍", "制造费比今年多（万元）", "每台制造费（元）", "年底交不出（台）", "晚交（台·月）"]),
              _line([":--", "--:", "--:", "--:", "--:"])]
    dem = sorted((r for r in rows if r.get("轴") == "需求系数" and r.get("运营成本_万元") != ""), key=lambda r: float(r["水平"]))
    for r in dem:
        if float(r["水平"]) < 1.1: continue
        parts.append(_line([f"{float(r['水平']):g} 倍", _wan(r["较参照_万元"], True), _wan(r["单车_元"]), r["流失"], r["延期台月"]]))
    hi = [r for r in dem if float(r["水平"]) >= 1]
    cliff = next((r for r in hi if int(float(r["流失"])) >= 100), None)
    small = [r for r in hi if int(float(r["流失"])) < 100]
    note = ""
    if cliff and small:
        last = small[-1]
        note = (f"放到 {float(last['水平']):g} 倍时交不出 {last['流失']} 台，可以当作还能交完。"
                f"从 {float(cliff['水平']):g} 倍起，交不出的台数要当回事。")
    parts += ["", note, "",
              "## 多出来的订单，三种办法对比", "",
              "对照都是「订单多到今年的 1.4 倍、又不采取下面的办法」。制造费变少，只说明少开了班，不代表多交了车。罚款不在制造费里。", "",
              _line(["办法（说人话）", "年底仍交不出（台）", "多交上（台）", "制造费（万元）", "人工", "能源", "车间和其他", "罚款另计"]),
              _line([":--", "--:", "--:", "--:", "--:", "--:", "--:", "--:"])]
    labels = {"需求×1.4且冲压产能+15%": "只把冲压加快 15%", "需求×1.4且焊装产能+15%": "只把焊装加快 15%",
              "需求×1.4且涂装产能+15%": "只把涂装加快 15%", "需求×1.4且总装产能+15%": "只把总装加快 15%",
              "需求×1.4且四车间产能+15%": "四条线都加快 15%", "需求×1.4且车型月上限+15%": "放宽每种车的月度上限 15%",
              "需求×1.4且成品库800元": "淡季提前造好，放仓库（每台每月 800 元）"}
    if d14:
        for name, label in labels.items():
            r = row(name)
            if r: parts.append(_line([label, r["流失"], int(float(d14["流失"])) - int(float(r["流失"])),
                                        _wan(r["较参照_万元"], True),
                                        _wan(r.get("人工差_万元", ""), True) if r.get("人工差_万元") != "" else "",
                                        _wan(r.get("能源差_万元", ""), True) if r.get("能源差_万元") != "" else "",
                                        _wan(r.get("车间差_万元", ""), True) if r.get("车间差_万元") != "" else "",
                                        _wan(r.get("罚款差_万元", ""), True) if r.get("罚款差_万元") != "" else ""]))
    parts += ["", "## 几条管理规定要花多少钱", "",
              "左边是按今年的订单。右边是订单比今年多两成、车仍能全部交上的时候。", "",
              _line(["规定", "今年多花（万元）", "订单多两成时多花（万元）"]),
              _line([":--", "--:", "--:"])]
    pairs = [("不许开夜班", "禁止三班", "需求×1.2且禁止三班"),
             ("每人每月加班不超过 24 小时", "加班上限24小时", "需求×1.2且加班上限24小时"),
             ("几乎不能再招人", "几乎不能加人", "需求×1.2且几乎不能加人"),
             ("不许把人借到别的车间", "禁止跨车间借调", "需求×1.2且禁止借调"),
             ("正常上班必须留出 15% 空档", "正常班利用率≤85%", "需求×1.2且正常班利用率≤85%")]
    for label, a, c in pairs:
        ra, rc = row(a), row(c)
        if ra and rc: parts.append(_line([label, _wan(ra["较参照_万元"], True), _wan(rc["较参照_万元"], True)]))
    low = [r for r in dem if float(r["水平"]) <= 0.6]
    if low:
        parts += ["", "## 订单少掉一大截", "",
                  "对照今年。车仍能交上时，每台制造费会升高，因为人工和车间开支摊到更少的车上。", "",
                  _line(["订单是今年的几倍", "制造费比今年（万元）", "每台制造费（元）", "年底交不出（台）"]),
                  _line([":--", "--:", "--:", "--:"])]
        for r in low:
            parts.append(_line([f"{float(r['水平']):g} 倍", _wan(r["较参照_万元"], True), _wan(r["单车_元"]), r["流失"]]))
    def _pack_table(title, intro, pairs):
        got = [(lb, r) for lb, name in pairs if (r := row(name))]
        if not got or not base: return
        parts.extend(["", f"## {title}", "", intro, "",
                      _line(["办法", "年底交不出（台）", "晚交（台·月）", "制造费比今年（万元）", "每台制造费（元）"]),
                      _line([":--", "--:", "--:", "--:", "--:"])])
        for lb, r in got:
            delta = float(r["运营成本_万元"]) - float(base["运营成本_万元"])
            parts.append(_line([lb, r["流失"], r["延期台月"], _wan(delta, True), _wan(r["单车_元"])]))
    _pack_table("订单多四成：月度上限最少放宽多少",
                "对照今年。交不出低于 100 台，就当作这档够用。",
                (("什么都不做", "需求×1.4"),
                 ("放宽 5%", "需求×1.4且月上限+5%"), ("放宽 8%", "需求×1.4且月上限+8%"),
                 ("放宽 10%", "需求×1.4且月上限+10%"), ("放宽 15%", "需求×1.4且车型月上限+15%")))
    _pack_table("订单多四成、又不改上限：仓库租金三档",
                "淡季提前造好放仓库。三档只是仓库收费不同。",
                (("什么都不做", "需求×1.4"),
                 ("每台每月 200 元", "需求×1.4且仓库200元"), ("每台每月 800 元", "需求×1.4且成品库800元"),
                 ("每台每月 2,000 元", "需求×1.4且仓库2000元")))
    _pack_table("订单多六成：几套办法放在一起",
                "对照今年。什么都不做会交不出一万多台，制造费也比「改完表再做」更高，因为班开得很满、车还是交不出。",
                (("什么都不做", "需求×1.6"),
                 ("只放宽月度上限 25%", "需求×1.6且月上限+25%"),
                 ("只把四条线加快 15%", "需求×1.6且四线加快15%"),
                 ("只提前造好放仓库", "需求×1.6且仓库800元"),
                 ("放宽上限，同时加快生产线", "需求×1.6且上限+25%且四线加快15%"),
                 ("放宽上限，同时放仓库", "需求×1.6且上限+25%且仓库800"),
                 ("上限、加快、仓库三件一起", "需求×1.6且上限四线仓库一起上"),
                 ("放宽上限，但不许夜班", "需求×1.6且上限+25%但不许夜班")))
    _pack_table("订单翻倍：几套办法放在一起",
                "对照今年。只改表就能在年底交完；加快生产线是为了少晚交、少花钱。",
                (("什么都不做", "需求×2"),
                 ("只放宽月度上限 60%", "需求×2且月上限+60%"),
                 ("放宽上限，同时把线加快 15%", "需求×2且上限+60%且四线加快15%"),
                 ("上限放宽、线加快 15%、再放仓库", "需求×2且上限四线仓库一起上"),
                 ("上限放宽、线加快 30%、再放仓库", "需求×2且上限+60%四线加快30%且仓库")))
    stacks = [r for r in rows if r.get("问题编号") == "stack" and r.get("运营成本_万元") != ""]
    if stacks and base:
        parts += ["", "## 几件坏事同时发生", "",
                  "制造费都是相对今年。「这套压力下」两行，是在「订单多四成、电费涨、工资涨、不许夜班」这堆坏事里，再改一个月度上限或改用仓库。", "",
                  _line(["发生了什么", "年底交不出（台）", "晚交（台·月）", "制造费比今年（万元）"]),
                  _line([":--", "--:", "--:", "--:"])]
        for r in stacks:
            delta = float(r["运营成本_万元"]) - float(base["运营成本_万元"])
            parts.append(_line([r["场景"], r["流失"], r["延期台月"], _wan(delta, True)]))
    parts += ["", "## 附录：另一份决策单", "",
              f"output/v5/管理层决策单.md 仍然可以看策略对比和安全边界，但不要和本页对到个位。那里的成本优先是 {sheet_cost}，求解误差 0.2%、大约 40 秒。它认定交不出 1 台，或某月积压超过 1,000 台，就算过不了，所以全年订单最多{sheet_bound}。本页以交不出 100 台为界，制造费用这一次 0.01%、60 秒的求解。",
              "",
              "用词：交不出 = 到年底还交不了；晚交 = 一台车晚一个月；制造费 = 人工、能源和车间费用，不含零件，也不含交不出的罚款；夜班 = 一天除白班外再开的班；月度上限 = 每种车每个月计划里允许做的最多台数。",
              ""]
    text = "\n".join(parts) + "\n"
    path = os.path.join(OUT, "决策说明.md")
    with open(path, "w", encoding="utf-8") as f: f.write(text)
    return text

def write_out(rows, found):
    os.makedirs(OUT, exist_ok=True)
    pub = [_public(r) for r in rows]
    with open(os.path.join(OUT, "cases.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(pub[0].keys())); w.writeheader(); w.writerows(pub)
    with open(os.path.join(OUT, "findings.csv"), "w", newline="", encoding="utf-8-sig") as f:
        fields = list(found[0].keys()) if found else ["问题编号", "问题", "结论"]
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(found)
    return write_brief(rows)

def main(only=None, procs=4, extreme=None):
    base = dl.load()
    on = extreme_enabled(extreme)
    cases = catalog(base, extreme=on)
    if only:
        want = set(only)
        # 参照场景必须在，否则 against 对不上
        need = want | {c["against"] for c in cases if c["name"] in want and c["against"]}
        cases = [c for c in cases if c["name"] in need]
    names = [c["name"] for c in cases]
    if len(names) != len(set(names)):
        raise SystemExit("情景名称重复：" + str([n for n in names if names.count(n) > 1]))
    print(f"推到极限：{'开' if on else '关'}。求解 {len(cases)} 个情景，并行 {procs}")
    solved = solve_all(base, cases, procs=procs)
    rows = build_rows(cases, solved)
    found = findings(rows)
    brief = write_out(rows, found)
    print(brief)
    print("简报：", os.path.join(OUT, "决策说明.md"))
    bad = [r["场景"] for r in rows if r["状态"] not in ("Optimal", "Not Solved")]
    if bad: print("\n未正常解出：", "、".join(bad))
    return rows, found

if __name__ == "__main__":
    import argparse
    from factory_analysis import main
    ap = argparse.ArgumentParser(description="工厂情景分析。推到极限默认看 data/switches.csv。")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--extreme", action="store_true", help="打开推到极限，忽略表格里的开关")
    g.add_argument("--no-extreme", action="store_true", help="关掉推到极限，忽略表格里的开关")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    main(procs=a.procs, extreme=True if a.extreme else False if a.no_extreme else None)
