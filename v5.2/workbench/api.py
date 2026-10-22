"""场景决策卡。数字只来自 engine.solve_case。正式 CSV 不改。"""
import csv, datetime, hashlib, json, os, subprocess
import data_loader as dl
import engine
from scenarios import apply_knobs, load_library

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(H, "output", "workbench")
LOG = os.path.join(OUT, "runs.jsonl")
SHOP = {"STP": "冲压", "BIW": "焊装", "PNT": "涂装", "TCF": "总装"}

# 网页滑块允许的范围。不在这里的键仍可由场景库带入，但要先出现在 scenarios.py 的旋钮里。
RANGES = {
    "demand_all": (0.7, 1.3),
    "elec": (0.8, 1.5),
    "wage": (0.8, 1.5),
    "gas": (0.8, 1.5),
    "ot": (0, 60),
    "dispatch": (0, 0.5),
    "stop_pay": (0.5, 1.0),
    "borrow": (0, 0.2),
    "penalty_mul": (0.1, 10),
    "max_shifts": (1, 3),
    "head_up": (0, 0.5),
    "head_dn": (0, 1),
    "post_switch_eff": (0.5, 1),
    "pm_days": (0, 10),
    "moq_fee": (0, 5_000_000),
    "restart_cost": (0, 5_000_000),
}
FACTOR_RANGE = (0.5, 1.3)   # 开动率、供应、按月/按车型需求系数
DOWN_RANGE = (0, 10)

EXERCISES = [
    {"id": "peak", "title": "例题 1 · 旺季冲量", "question": "9–12 月需求涨 15%，成本和班次会怎样？", "scenario": "旺季冲量"},
    {"id": "elec", "title": "例题 2 · 电价上浮两成", "question": "电价涨两成，多花多少？班次改不改？", "knobs": {"elec": 1.2}},
    {"id": "down", "title": "例题 3 · 焊装停一周", "question": "焊装 6 月停 5 个工作日，靠什么补产量？", "scenario": "焊装停线一周"},
]

ENERGY_KEYS = ("能源", "启停", "需量")
SKIP_ACCOUNT = ("物料",)


def code_version():
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=H, stderr=subprocess.DEVNULL, text=True
        ).strip()
        if rev:
            return rev
    except Exception:
        pass
    blob = b"".join(open(os.path.join(H, n), "rb").read() for n in
                    ("model_builder.py", "cost_functions.py", "energy.py", "report.py", "scenarios.py"))
    return "src-" + hashlib.sha1(blob).hexdigest()[:8]


def library():
    return load_library()


def exercise_knobs(item):
    if item.get("scenario"):
        lib = {r["name"]: r for r in library()}
        row = lib[item["scenario"]]
        return row["knobs"], row["name"], row["description"]
    return dict(item.get("knobs") or {}), item["title"], item["question"]


def validate(knobs):
    """越界的旋钮拒绝提交。场景库里已有的组合也走同一套范围。"""
    k = knobs or {}
    bad = []
    for key, (lo, hi) in RANGES.items():
        if key in k and not (lo <= float(k[key]) <= hi):
            bad.append(f"{key} 应在 {lo}–{hi}")
    for key in ("demand_month", "demand_model", "avail", "supply"):
        for name, val in (k.get(key) or {}).items():
            if not (FACTOR_RANGE[0] <= float(val) <= FACTOR_RANGE[1]):
                bad.append(f"{key}.{name} 应在 {FACTOR_RANGE[0]}–{FACTOR_RANGE[1]}")
    for key in ("demand_all",):
        pass
    for name, val in (k.get("demand_cell") or {}).items():
        if not (0.5 <= float(val) <= 1.5):
            bad.append(f"demand_cell.{name} 应在 0.5–1.5")
    for name, val in (k.get("down") or {}).items():
        if not (DOWN_RANGE[0] <= float(val) <= DOWN_RANGE[1]):
            bad.append(f"停线 {name} 应在 {DOWN_RANGE[0]}–{DOWN_RANGE[1]} 天")
    if "tou_version" in k and str(k["tou_version"]) not in ("2024", "2026"):
        bad.append("分时电价版本只能是 2024 或 2026")
    if "max_shifts" in k and int(k["max_shifts"]) not in (1, 2, 3):
        bad.append("最多班次只能是 1、2 或 3")
    return bad


def _wan(yuan):
    return round(yuan / 1e4)


def _energy(cost):
    return sum(v for k, v in cost.items() if k.startswith(ENERGY_KEYS))


def _ot(cost):
    return cost.get("加班", 0) + cost.get("超限加班溢价", 0)


def compress_shifts(plan, shops):
    """把 12 个月的 30x2 串收成『全年』或『5月、10月』。"""
    lines = []
    for s in shops:
        rows = sorted((r for r in plan if r["shop"] == s), key=lambda r: r["month"])
        groups = []
        for r in rows:
            key = (int(round(r["jph"])), int(r["shifts"]))
            if groups and groups[-1][0] == key:
                groups[-1][1].append(int(r["month"]))
            else:
                groups.append((key, [int(r["month"])]))
        parts = []
        for (jph, shifts), months in groups:
            label = f"{jph} JPH × {shifts} 班"
            if months == list(range(1, 13)):
                parts.append(f"全年 {label}")
            elif len(months) == 1:
                parts.append(f"{months[0]} 月 {label}")
            elif months == list(range(months[0], months[-1] + 1)):
                parts.append(f"{months[0]}–{months[-1]} 月 {label}")
            else:
                parts.append(f"{'、'.join(str(m) for m in months)} 月 {label}")
        lines.append(f"{SHOP.get(s, s)}：" + "；".join(parts))
    return lines


def shift_changes(base_lines, new_lines):
    out = []
    for a, b in zip(base_lines, new_lines):
        if a != b:
            shop = b.split("：", 1)[0]
            out.append(f"{shop}由「{a.split('：', 1)[1]}」改为「{b.split('：', 1)[1]}」")
    return out


def _pack(solved, shops):
    k, cost = solved["kpi"], solved["cost"]
    return dict(
        状态=solved["status"],
        运营成本_万元=_wan(k["运营成本"]),
        单车_元=round(k["单车成本"]),
        产量=round(solved["out"]),
        延期台月=round(k["延期台月"]),
        流失台=round(k["流失台"]),
        加班_万元=_wan(_ot(cost)),
        能源_万元=_wan(_energy(cost)),
        班次=compress_shifts(solved["plan"], shops),
        哈希=solved.get("hash", ""),
        缓存=bool(solved.get("cached")),
    )


def top_accounts(base_cost, new_cost, n=3):
    keys = set(base_cost) | set(new_cost)
    rows = []
    for key in keys:
        if key in SKIP_ACCOUNT or key.startswith("权重"):
            continue
        delta = _wan(new_cost.get(key, 0) - base_cost.get(key, 0))
        if delta:
            rows.append({"科目": key, "差额_万元": delta})
    rows.sort(key=lambda r: abs(r["差额_万元"]), reverse=True)
    return rows[:n]


def borrow_net(cost):
    save = cost.get("借调节省人工", 0)
    occupy = cost.get("借调占用(借出方停工日不能省)", cost.get("借调占用", 0))
    return save + occupy


def unverified_lines(cost):
    net = borrow_net(cost)
    if abs(net) < 50e4:
        return []
    return [f"借调净额 {_wan(net):+,} 万元，未验证。按天核对同一天有没有空人之前，不要写成已经省下的钱。"]


def warnings_for(knobs, new_cost, status):
    """最多 4 条。只在这笔结果真的用到该假设时挂上。"""
    items = []
    if abs(borrow_net(new_cost)) >= 50e4:
        items.append(dict(编号="A03", 负责人="生产部/人事部",
                          文字="未验证。月度借调按人·天凑平。按天核对同一天有没有空人之前，这笔净额不要写成已经省下的钱。"))
    if knobs.get("dispatch", 0.2) >= 0.1 or "dispatch" not in knobs:
        items.append(dict(编号="A01", 负责人="人事部",
                          文字="派遣加临时工占比示例为 20%。法规派遣上限是用工总量的 10%，口径要 HR 确认。"))
    if any(x in knobs for x in ("elec", "gas", "tou_version", "voltage", "weekend_policy")):
        items.append(dict(编号="A11", 负责人="能源/设备部",
                          文字="电价、气价、启停和分时参数仍是行业暂定。"))
    if "stop_pay" in knobs:
        items.append(dict(编号="A02", 负责人="人事部/财务部",
                          文字="停工日发薪比例改变了可省人工，正式工比例要符合当地停工工资规定。"))
    if status != "Optimal":
        items.insert(0, dict(编号="求解", 负责人="AI & Data",
                             文字=f"求解状态是 {status}。时限内可能停在另一个可行解上，和上次的差额要先看时限再看公式。"))
    # 默认模型总是用到派遣比。没有能源旋钮时不必占一栏。
    if not any(x in knobs for x in ("elec", "gas", "tou_version", "voltage", "weekend_policy")):
        items = [x for x in items if x["编号"] != "A11"]
    return items[:4]


def render_card(card):
    b, s = card["基准"], card["本次"]
    delta = s["运营成本_万元"] - b["运营成本_万元"]
    pct = (delta / b["运营成本_万元"] * 100) if b["运营成本_万元"] else 0
    lines = [
        "# 决策卡",
        "",
        "示例数据。金额由求解器算出，不能手改。",
        "",
        f"问题：{card['问题']}",
        f"配置 {card['配置版本']} · 代码 {card['代码版本']} · {card['运行时间']} · 结果 {card['结果哈希']}",
        f"场景：{card['名称']} · 求解 {s['状态']} · 对照：基准",
        "旋钮：" + (json.dumps(card["旋钮"], ensure_ascii=False) if card["旋钮"] else "无"),
        "",
        "## ① 结果",
        "",
        f"全年运营成本 {s['运营成本_万元']:,} 万元，单车 {s['单车_元']:,} 元，产量 {s['产量']:,} 台。",
        "延期 {0} 台·月，流失 {1} 台。".format(s["延期台月"], s["流失台"]),
        "",
        *[f"- {x}" for x in s["班次"]],
        "",
        "## ② 多花多少",
        "",
        f"比基准 {b['运营成本_万元']:,} 万元 {delta:+,} 万元（{pct:+.2f}%）。对照的是基准运营成本，不是策略扫描里的成本优先。",
        "",
    ]
    for line in card.get("未验证") or []:
        lines.append(line)
    if card.get("未验证"):
        lines.append("")
    lines += [
        "## ③ 为什么",
        "",
    ]
    for w in card["为什么"]:
        lines.append(f"- {w}")
    lines += ["", "## ④ 风险", "", card["风险"], "", "## ⑤ 待确认", ""]
    for w in card["待确认"]:
        lines.append(f"- {w['编号']}（{w['负责人']}）{w['文字']}")
    if card.get("拍板"):
        lines += ["", "## 需要拍板", ""]
        for x in card["拍板"]:
            lines.append(f"- {x}")
    lines.append("")
    return "\n".join(lines)


def _why(base, cur, accounts):
    why = []
    why.append(f"产量 {base['产量']:,} → {cur['产量']:,} 台，延期 {base['延期台月']} → {cur['延期台月']} 台·月，流失 {base['流失台']} → {cur['流失台']} 台。")
    changed = shift_changes(base["班次"], cur["班次"])
    why.append("班次：" + ("；".join(changed) if changed else "各车间与基准相同。"))
    if accounts:
        bits = [f"{a['科目']} {a['差额_万元']:+,} 万" for a in accounts]
        why.append("科目差额最大的是 " + "，".join(bits) + "。")
    else:
        why.append("科目差额都小于 1 万元。")
    return why


def run(question, knobs=None, name="自定义", decisions=None, source="cli"):
    knobs = knobs or {}
    bad = validate(knobs)
    if bad:
        raise ValueError("；".join(bad))
    base_d = dl.load()
    shops = list(base_d["shops"])
    d = apply_knobs(base_d, knobs) if knobs else base_d
    base = engine.solve_case(base_d, "基准")
    cur = engine.solve_case(d, name or "自定义")
    packed_b, packed = _pack(base, shops), _pack(cur, shops)
    accounts = top_accounts(base["cost"], cur["cost"])
    card = dict(
        种类="场景",
        问题=question or name,
        名称=name or "自定义",
        配置版本=base_d["plant"].get("config_version", ""),
        代码版本=code_version(),
        运行时间=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        结果哈希=packed["哈希"],
        旋钮=knobs,
        基准=packed_b,
        本次=packed,
        科目差=accounts,
        为什么=_why(packed_b, packed, accounts),
        未验证=unverified_lines(cur["cost"]),
        风险="本次未做样本风险，没有 P90，也没有超预算概率。求解状态：{}。".format(packed["状态"]),
        待确认=warnings_for(knobs, cur["cost"], packed["状态"]),
        拍板=list(decisions or []),
        示例数据=True,
    )
    card["正文"] = render_card(card)
    os.makedirs(OUT, exist_ok=True)
    rec = {k: card[k] for k in ("问题", "名称", "配置版本", "代码版本", "运行时间", "结果哈希", "旋钮")}
    rec["来源"] = source
    rec["运营成本_万元"] = packed["运营成本_万元"]
    rec["比基准_万元"] = packed["运营成本_万元"] - packed_b["运营成本_万元"]
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    path = os.path.join(OUT, f"{card['运行时间'].replace(' ', '_').replace(':', '')}_{name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(card["正文"])
    card["文件"] = path
    return card


def load_source_map():
    path = os.path.join(H, "data", "data_source_map.csv")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_assumptions():
    path = os.path.join(H, "data", "假设登记表.csv")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    import argparse
    p = argparse.ArgumentParser(description="跑一个场景并写出决策卡")
    p.add_argument("--scenario", default="")
    p.add_argument("--knobs", default="")
    p.add_argument("--question", default="")
    a = p.parse_args()
    if a.scenario:
        row = next(r for r in library() if r["name"] == a.scenario)
        knobs, name, desc = row["knobs"], row["name"], row["description"]
        question = a.question or desc
    elif a.knobs:
        knobs, name = json.loads(a.knobs), "自定义"
        question = a.question or name
    else:
        item = EXERCISES[1]
        knobs, name, question = item["knobs"], item["title"], item["question"]
    card = run(question, knobs, name, source="cli")
    print(card["正文"])
    print("\n已写入", card["文件"])


if __name__ == "__main__":
    main()
