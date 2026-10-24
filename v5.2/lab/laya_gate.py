"""Laya 只做选择题。台数和制造费来自已经算好的情景，对不上就否决。

求解器、目标函数和旋钮都不用改。本文件读 output/analysis/cases.csv。
运行（需要 Apple 芯片上的 laya-mlx）：

  ../laya-mlx-main/.venv/bin/python lab/laya_gate.py
"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import csv, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(HERE, "output", "analysis", "cases.csv")
MODEL = "aac6fef/laya-multilingual-mlx"

# 选项里写上现场会说的原词。中文输入用 multilingual 检查点。
QUESTIONS = {
    "demand": {
        "type": "choice",
        "instructions": "订单比今年多多少？",
        "criteria": {
            "y14": "多四成，今年的 1.4 倍",
            "y16": "多六成，今年的 1.6 倍",
            "y20": "翻倍，今年的 2 倍",
            "unclear": "没有说清是哪一档",
        },
    },
    "cap": {
        "type": "choice",
        "instructions": "每种车每个月的上限能不能改？",
        "criteria": {
            "planning": "只是计划表，可以改",
            "hard": "模具、客户订单或码头定死的，改不了",
            "unclear": "没有说清能不能改",
        },
    },
    "hire": {
        "type": "choice",
        "instructions": "新招的人什么时候能上线？",
        "criteria": {
            "this_month": "这个月就能到岗",
            "lead_time": "要一到三个月，两个月或三个月后才能到岗",
            "unclear": "没有说什么时候能到岗",
        },
    },
    "night": {
        "type": "choice",
        "instructions": "能不能在白班以外再开夜班？",
        "criteria": {
            "allowed": "夜班可以开",
            "banned": "不许开夜班",
            "unclear": "没有说夜班",
        },
    },
    "ask": {
        "type": "choice",
        "instructions": "说话的人想先试哪一种办法？",
        "criteria": {
            "raise_cap": "先改月度上限那张表",
            "speed_line": "先把生产线加快",
            "warehouse": "淡季提前造好放进仓库",
            "unclear": "没有指定这三种办法",
        },
    },
}

# 原话里已经写死的词。Laya 把握不够时用它补上；和原话相反时改判。
PHRASES = {
    "demand": (("y14", ("多出四成", "多四成", "1.4")), ("y16", ("多六成", "1.6")), ("y20", ("翻倍", "两倍"))),
    "cap": (("hard", ("定死", "改不了")), ("planning", ("计划表", "可以改"))),
    "hire": (("lead_time", ("两个月", "三个月", "一到三个月")), ("this_month", ("这个月就能", "这个月可以"))),
    "night": (("banned", ("不许开夜班", "不能开夜班", "禁止夜班")), ("allowed", ("夜班可以", "可以开夜班"))),
    "ask": (("speed_line", ("加快",)), ("warehouse", ("放进仓库", "放仓库")), ("raise_cap", ("改那张", "改表"))),
}

BANDS = {
    "y14": {
        "label": "订单是今年的 1.4 倍",
        "base": "需求×1.4",
        "speed": "需求×1.4且四车间产能+15%",
        "cap": "需求×1.4且车型月上限+15%",
        "warehouse": "需求×1.4且成品库800元",
        "cap_night": "需求×1.4且上限+15%但不许夜班",
    },
    "y16": {
        "label": "订单是今年的 1.6 倍",
        "base": "需求×1.6",
        "speed": "需求×1.6且四线加快15%",
        "cap": "需求×1.6且月上限+25%",
        "warehouse": "需求×1.6且仓库800元",
        "cap_night": "需求×1.6且上限+25%但不许夜班",
    },
    "y20": {
        "label": "订单是今年的 2 倍",
        "base": "需求×2",
        "speed": None,
        "cap": "需求×2且月上限+60%",
        "warehouse": None,
        "cap_night": None,
    },
}
ASK_NAME = {"raise_cap": "改月度上限", "speed_line": "加快生产线", "warehouse": "淡季放仓库", "unclear": "没有指定办法"}


def load_cases(path=CASES):
    with open(path, encoding="utf-8-sig") as f:
        return {r["场景"]: r for r in csv.DictReader(f)}


def _lost(row):
    return int(float(row["流失"]))


def _num(row, key):
    return float(row[key])


def _clears(row):
    return _lost(row) < 100


def read_answers(raw, min_conf=0.45):
    """置信度不够，或选了 unclear，这道题就不拿来改建议。"""
    picks, weak = {}, []
    for key in QUESTIONS:
        ans = raw[key]
        choice = ans["choice"]
        if ans["confidence"] < min_conf or choice == "unclear":
            weak.append(key)
            choice = "unclear"
        picks[key] = choice
    return picks, weak


def apply_phrases(state, picks, weak):
    """原话里的原词优先于模型。把握不够时补上，说反了就改判。"""
    notes = []
    for key, rules in PHRASES.items():
        hit = None
        for choice, words in rules:
            word = next((w for w in words if w in state), None)
            if word:
                hit = (choice, word)
                break
        if not hit or picks.get(key) == hit[0]:
            continue
        notes.append(f"原话有「{hit[1]}」，{key} 从 {picks.get(key)} 改为 {hit[0]}")
        picks[key] = hit[0]
        if key in weak:
            weak.remove(key)
    return notes


def _money(row):
    who = row.get("参照") or "参照"
    return (f"对账（对照{who}）：制造费 {float(row['较参照_万元']):+,.1f} 万"
            f" = 人工 {float(row['人工差_万元']):+,.1f} 万"
            f" + 能源 {float(row['能源差_万元']):+,.1f} 万"
            f" + 车间和其他 {float(row['车间差_万元']):+,.1f} 万。"
            f"交不出的罚款另计 {float(row['罚款差_万元']):+,.1f} 万，不在制造费里。")


def verdict(raw, rows, state="", min_conf=0.45):
    """用求解结果否决 Laya 收进来的办法。raw 是 predict()['answers']。"""
    picks, weak = read_answers(raw, min_conf)
    notes = apply_phrases(state, picks, weak) if state else []
    band = BANDS.get(picks["demand"])
    if band is None:
        return dict(ok=False, picks=picks, weak=weak, action=None, notes=notes, text=(
            "订单倍数没有落到今年的 1.4 倍、1.6 倍或 2 倍上，这次不报台数。"
            "把订单说成这三档之一后再问。"
        ))
    need = [band["base"], band["cap"]]
    for key in ("speed", "warehouse", "cap_night"):
        if band[key]:
            need.append(band[key])
    missing = [n for n in need if n not in rows]
    if missing:
        return dict(ok=False, picks=picks, weak=weak, action=None, notes=notes, text="缺少已求解的情景：" + "、".join(missing))

    base, cap = rows[band["base"]], rows[band["cap"]]
    speed = rows[band["speed"]] if band["speed"] else None
    warehouse = rows[band["warehouse"]] if band["warehouse"] else None
    cap_night = rows[band["cap_night"]] if band["cap_night"] else None
    lines = [f"按已经算过的情景，{band['label']}。什么都不做，年底交不出 {_lost(base)} 台。"]
    veto = []

    if picks["ask"] == "speed_line":
        if speed is None:
            veto.append("这一档没有单独的「只加快生产线」情景，不能用加快生产线作为建议。")
        elif _lost(speed) > _lost(base) - 100:
            veto.append(f"说话的人想先加快生产线。求解结果是交不出的仍是 {_lost(speed)} 台，和什么都不做一样。这条否决。")
        lines.append(veto[-1] if veto else f"加快生产线后，交不出的降到 {_lost(speed)} 台。")

    hard = picks["cap"] == "hard"
    night_off = picks["night"] == "banned"
    if hard:
        lines.append("月度上限被说成模具、客户订单或码头的硬限制，所以不建议改那张表。")
        if warehouse is None:
            lines.append("这一档没有仓库情景，这次给不出放仓库的台数。")
            action = None
        elif _clears(warehouse):
            lines.append(f"改用淡季提前造好放仓库，年底可以交完。{_money(warehouse)}")
            action = "warehouse"
        else:
            lines.append(f"只放仓库，年底仍交不出 {_lost(warehouse)} 台。月度上限把每个月能做的量卡住了，淡季也存不出后来要交的车。")
            action = None
    else:
        if picks["cap"] == "unclear":
            lines.append("没说清月度上限能不能改。下面先按「能改」算；如果其实是模具或码头限制，改看放仓库。")
        use = cap
        action = "raise_cap"
        if night_off and cap_night is not None:
            use = cap_night
            if not _clears(cap_night):
                lines.append(f"不许开夜班之后，只放宽月度上限还交不出 {_lost(cap_night)} 台。要么允许夜班，要么在改表之外再加快生产线。")
                action = None
            else:
                late = int(float(cap_night["延期台月"]))
                lines.append(f"不许开夜班，表改完年底仍能交完。"
                             + (f"晚交 {late} 个「一台晚一个月」。" if late >= 200 else "晚交可以忽略。")
                             + _money(cap_night))
        elif _clears(cap):
            lines.append(f"先把月度上限放宽，这 {_lost(base)} 台可以交上。{_money(cap)}")
        else:
            lines.append(f"只放宽月度上限，年底仍交不出 {_lost(cap)} 台。")
            action = None
        if picks["ask"] == "warehouse" and warehouse is not None and _clears(warehouse) and _clears(cap):
            lines.append(f"说话的人想放仓库。仓库也能交完，{_money(warehouse)}上限能改的时候，改表更便宜。")

    if picks["hire"] == "lead_time" and action == "raise_cap":
        lines.append("人要一到三个月才能到岗。求解器里一月份可以一次招满，所以「改表就能交上」在用人上偏乐观。可信程度：模型算不出。")
    elif picks["hire"] == "this_month":
        lines.append("按这句话，人这个月可以到岗。人数仍跟着速度档走，不能单独加人、速度保持不变。")

    if "demand" in weak:
        lines.append("订单这一档的把握不高，台数先不要拿去拍板。")
    return dict(ok=True, picks=picks, weak=weak, action=action, text="".join(lines), veto=veto, notes=notes)


SAMPLES = [
    "订单要比今年多出四成。月度上限只是计划表，模具和码头还能加。人要两个月才能到岗。夜班可以开。我们想先把四条线都加快。",
    "订单多四成。每种车每个月的上限是模具定死的，改不了。夜班可以开。可以接受淡季提前造好放进仓库。",
    "订单多六成。月度上限可以改。不许开夜班。人这个月就能招齐。想先改那张月度上限的表。",
]


def _show(raw):
    parts = []
    for key, ans in raw.items():
        probs = ans.get("probabilities") or {}
        top = "、".join(f"{k} {v:.0%}" for k, v in sorted(probs.items(), key=lambda kv: -kv[1])[:3])
        parts.append(f"{key}={ans['choice']}（{ans['confidence']:.0%}；{top}）")
    return "；".join(parts)


def main(states=None):
    rows = load_cases()
    import laya_mlx as laya
    agent = laya.load(MODEL)
    for i, state in enumerate(states or SAMPLES, 1):
        raw = agent.predict(state, QUESTIONS)["answers"]
        out = verdict(raw, rows, state)
        print(f"\n[{i}] {state}")
        print("Laya：", _show(raw))
        if out.get("notes"):
            print("安全层：", "；".join(out["notes"]))
        print(out["text"])
        print("采纳：", ASK_NAME.get(out["action"], "这句里没有可执行的办法"))


if __name__ == "__main__":
    main(sys.argv[1:] or None)
