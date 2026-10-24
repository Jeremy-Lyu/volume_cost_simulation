"""工厂配置包检查（多工厂复制，第 21 节）：结构校验 + 业务规则校验 + 就绪度打分（示例）
用法：python3 plant_check.py [配置包目录]   默认 data/（示例配置包）
输出：控制台报告 + output/readiness_<plant_id>.md
说明：核心标准 = 下面的 SCHEMA（文件、字段）和 RULES（业务规则）；工厂只提供数据，不改代码。"""
import csv, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = {   # 核心参数表标准（core-1.0）：文件 -> 必填字段
    "plant.json":        ["plant_id", "shops", "core_version", "config_version"],
    "demand.csv":        ["month", "model", "demand"],
    "calendar.csv":      ["month", "workdays"],
    "capacity_limit.csv":["shop", "model", "month", "cap"],
    "jph_options.csv":   ["shop", "jph", "heads_per_shift", "run_kw"],
    "shift_options.csv": ["shifts", "eff_hours_per_shift", "night_allowance_per_head", "bus_cost_per_shift_month", "outsourcing_per_shift_month"],
    "shop_params.csv":   ["shop", "kwh_per_unit", "oh_fixed_month", "oh_var_per_unit", "ot_max_hours_month", "buffer_cap", "hold_cost_per_unit_month"],
    "global_params.csv": ["key", "value"],
}
GLOBAL_KEYS = ["wage_per_head_month", "std_hours_month", "ot_multiplier", "elec_price", "shortage_penalty", "solver_time_limit"]
OPTIONAL = {   # 可选表：文件 -> (说明, 必填字段)；缺文件 = 不启用该扩展（口径与基础版一致）
    "actual.csv":           ("实际数据（回测对账用）", ["shop", "month", "volume"]),
    "scenario_library.csv": ("本厂场景库（可选，默认用核心场景库）", ["name", "category", "description", "knobs"]),
    "mat_cost.csv":         ("物料单车成本（model, month, cost_per_unit；month=0 为默认）", ["model", "month", "cost_per_unit"]),
    "quality.csv":          ("一次合格率 FTT（返修占用产线时间 → 有效产能折损）", ["shop", "ftt"]),
    "ramp.csv":             ("爬坡系数（新车型导入期降速）", ["shop", "month", "factor"]),
    "shipping_cap.csv":     ("发运能力上限（整车物流/库容/承运商运力）", ["model", "month", "cap"]),
    "indirect.csv":         ("间接人员定员（按 JPH 档）", ["shop", "jph", "heads_per_shift"]),
    "changeover.csv":       ("换型换色（次数×每次小时与费用）", ["shop", "setups_per_month", "hours_per_setup", "cost_per_setup"]),
    "carrier.csv":          ("滑橇/吊具数量（有效缓存上限 = min(库容, 载体数)）", ["shop", "carriers"]),
    "logistics.csv":        ("成品发运模式（capacity, cost_per_trip, fixed_month_cost）", ["lane", "mode", "capacity", "cost_per_trip"]),
    "tooling.csv":          ("模具工装月摊销", ["model", "month", "monthly_amount"]),
    "asset.csv":            ("设备月折旧（用则须从 OH 扣除折旧避免重复）", ["shop", "monthly_depreciation"]),
    "margin.csv":           ("边际贡献（售价−物料−变动物流；替代缺口惩罚，物料只做口径）", ["model", "month", "margin_per_unit"]),
    "oee.csv":              ("OEE 时间开动率×性能开动率（把 avail 拆开）", ["shop", "month", "time_rate", "perf_rate"]),
    "attendance.csv":       ("出勤率（单列）", ["shop", "month", "rate"]),
    "avail.csv":            ("静态限产/开动率（环保限产、政策停产等）", ["shop", "month", "rate"]),
    "rework.csv":           ("返修区能力与质量成本", ["shop", "stations", "hours_per_unit", "cost_per_hour", "scrap_rate", "scrap_cost_per_unit"]),
    "models.csv":           ("车型工时等级/颜色（涂装换色与 weekly.py）", ["model", "config_load", "color"]),
    "color_batch.csv":      ("换色最小批量（涂装颜色缓冲）", ["color", "batch"]),
    "skill.csv":            ("技能覆盖检查（weekly.py 事后核对，不进月模型）", ["station", "required_per_shift"]),
    "line_supply.csv":      ("叫料与线前库存（calloff_cap, git_incoming, safety_buffer）", ["model", "month", "calloff_cap"]),
    "capacity_component.csv": ("三厂能力分量（同一车型月取最小）", ["plant", "model", "month", "max_orders"]),
    "part_price.csv":       ("零件原币价格×汇率，优先于 mat_cost", ["model", "month", "price", "currency", "fx_rate"]),
    "slot_cap.csv":         ("周计划回写的槽位产量上限", ["model", "month", "cap"]),
    "coarse_params.csv":    ("六个粗参数。value 为空或 0/1 时不改变现成本", ["key", "value", "example"]),
}
GLOBAL_KEYS_OPT = {"burden_rate": 1.0, "capital_rate_month": 0.0, "warranty_per_unit": 0.0, "carbon_cost_per_unit": 0.0}
CORE_SUPPORTED = {"core-1.0"}

def rd(base, n):
    with open(os.path.join(base, n), encoding="utf-8") as f: return list(csv.DictReader(f))

def check(base):
    res = []   # (类别, 检查项, 结果 PASS/FAIL/WARN, 说明)
    add = lambda c, i, ok, msg="": res.append((c, i, ok, msg))
    # 1 结构：文件和字段
    plant = {}
    for fn, cols in SCHEMA.items():
        p = os.path.join(base, fn)
        if not os.path.exists(p): add("结构", fn, "FAIL", "缺文件"); continue
        if fn.endswith(".json"):
            plant = json.load(open(p, encoding="utf-8")); miss = [c for c in cols if c not in plant]
        else:
            with open(p, encoding="utf-8") as f: hdr = next(csv.reader(f))
            miss = [c for c in cols if c not in hdr]
        add("结构", fn, "FAIL" if miss else "PASS", f"缺字段 {miss}" if miss else "")
    if any(r[2] == "FAIL" for r in res): return plant, res
    shops = plant["shops"]
    add("版本", "核心版本兼容", "PASS" if plant["core_version"] in CORE_SUPPORTED else "FAIL", plant["core_version"])
    g = {r["key"]: r["value"] for r in rd(base, "global_params.csv")}
    miss = [k for k in GLOBAL_KEYS if k not in g]; add("结构", "全局参数齐全", "FAIL" if miss else "PASS", f"缺 {miss}" if miss else "")
    # 2 完整性：每个 车间×车型×月 都有产能上限，每月有日历，每车间有 JPH 档和车间参数
    dem = rd(base, "demand.csv"); months = sorted({int(r["month"]) for r in dem}); models = sorted({r["model"] for r in dem})
    cal = {int(r["month"]) for r in rd(base, "calendar.csv")}
    add("完整性", "日历覆盖需求月份", "PASS" if set(months) <= cal else "FAIL", f"缺 {sorted(set(months)-cal)}" if not set(months) <= cal else "")
    cap = {(r["shop"], r["model"], int(r["month"])) for r in rd(base, "capacity_limit.csv")}
    gap = [(s, m, t) for s in shops for m in models for t in months if (s, m, t) not in cap]
    add("完整性", "产能上限 车间×车型×月", "PASS" if not gap else "FAIL", f"缺 {len(gap)} 格，如 {gap[:3]}" if gap else f"{len(shops)}×{len(models)}×{len(months)}")
    jph = {}
    for r in rd(base, "jph_options.csv"): jph.setdefault(r["shop"], []).append(r)
    sp = {r["shop"] for r in rd(base, "shop_params.csv")}
    for s in shops:
        add("完整性", f"{s} JPH档", "PASS" if jph.get(s) else "FAIL", f"{len(jph.get(s, []))} 档")
        add("完整性", f"{s} 车间参数", "PASS" if s in sp else "FAIL")
    extra = sorted(set(jph) - set(shops)); add("一致性", "JPH档车间都在车间链里", "WARN" if extra else "PASS", f"多余 {extra}" if extra else "")
    # 3 业务规则（实体框架「规则」层，示例）
    for s, opts in jph.items():
        o = sorted(opts, key=lambda r: float(r["jph"]))
        mono = all(float(a["heads_per_shift"]) < float(b["heads_per_shift"]) and float(a["run_kw"]) <= float(b["run_kw"]) for a, b in zip(o, o[1:]))
        add("规则", f"{s} 定员/功率随 JPH 档单调递增", "PASS" if mono else "FAIL")
    bad = [r["month"] for r in rd(base, "calendar.csv") if not 0 < float(r["workdays"]) <= 31]
    add("规则", "工作日在 1–31", "FAIL" if bad else "PASS", f"异常月 {bad}" if bad else "")
    sh = rd(base, "shift_options.csv")
    hrs = [float(r["eff_hours_per_shift"]) * int(r["shifts"]) for r in sh]
    add("规则", "每日有效小时 ≤ 24", "PASS" if max(hrs) <= 24 else "FAIL", f"最大 {max(hrs)}")
    ot = [float(r["ot_max_hours_month"]) for r in rd(base, "shop_params.csv")]
    add("规则", "加班上限 ≤ 36h/月（劳动法规则，⚠ 按当地法规配置）", "PASS" if max(ot) <= 36 else "WARN", f"最大 {max(ot)}")
    # 4 可选扩展表：缺文件=未启用（WARN）；有文件=校验字段与取值规则
    def _orows(fn): return rd(base, fn) if os.path.exists(os.path.join(base, fn)) else []
    for fn, (desc, cols) in OPTIONAL.items():
        p = os.path.join(base, fn)
        if not os.path.exists(p): add("可选", fn, "WARN", "未启用：" + desc); continue
        with open(p, encoding="utf-8") as f: hdr = next(csv.reader(f))
        miss = [c for c in cols if c not in hdr]
        add("可选", fn, "FAIL" if miss else "PASS", f"缺字段 {miss}" if miss else desc)
    q = _orows("quality.csv")
    if q:
        bad = [r["shop"] for r in q if not 0 < float(r["ftt"]) <= 1]
        add("规则", "FTT 在 (0,1]", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    rmp = _orows("ramp.csv")
    if rmp:
        bad = [f"{r['shop']}月{r['month']}" for r in rmp if not 0 < float(r["factor"]) <= 1]
        add("规则", "爬坡系数在 (0,1]", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    mc = _orows("mat_cost.csv")
    if mc:
        bad = [r["model"] for r in mc if float(r["cost_per_unit"]) < 0]
        add("规则", "物料单车成本 ≥ 0", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    cc = _orows("carrier.csv")
    if cc:
        bad = [r["shop"] for r in cc if float(r["carriers"]) < 0]
        add("规则", "滑橇/吊具数量 ≥ 0", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    br = float(g.get("burden_rate", 1) or 1); cr = float(g.get("capital_rate_month", 0) or 0)
    add("规则", "福利社保系数 burden_rate ≥ 1", "PASS" if br >= 1 else "FAIL", f"burden_rate={br}")
    add("规则", "库存资金月利率 ≥ 0", "PASS" if cr >= 0 else "FAIL", f"capital_rate_month={cr}")
    for fn, cols in (("oee.csv", ("time_rate", "perf_rate")), ("attendance.csv", ("rate",)), ("avail.csv", ("rate",))):
        rows_ = _orows(fn)
        if rows_:
            bad = [r for r in rows_ if not all(0 < float(r[c]) <= 1 for c in cols)]
            add("规则", f"{fn} 取值在 (0,1]", "FAIL" if bad else "PASS", f"异常 {len(bad)} 行" if bad else "")
    rw = _orows("rework.csv")
    if rw:
        bad = [r["shop"] for r in rw if float(r["stations"]) <= 0 or float(r["hours_per_unit"]) < 0]
        add("规则", "返修区工位数 > 0 且返修工时 ≥ 0", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    ls = _orows("line_supply.csv")
    if ls:
        bad = [r["model"] for r in ls if not 0 <= float(r.get("scrap_rate") or 0) <= 1 or not 0 <= float(r.get("cancel_rate") or 0) <= 1 or float(r["calloff_cap"]) < 0]
        add("规则", "叫料上限≥0 且报废/冲销率在 [0,1]", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    pp = _orows("part_price.csv")
    if pp:
        bad = [r["model"] for r in pp if float(r["price"]) < 0 or float(r["fx_rate"]) <= 0]
        add("规则", "零件价≥0 且汇率>0", "FAIL" if bad else "PASS", f"异常 {bad}" if bad else "")
    chg = _orows("changeover.csv")
    if any((r.get("mode") or "") == "color" for r in chg):
        colors = {r["model"] for r in _orows("models.csv") if r.get("color")}
        dem_models = {r["model"] for r in rd(base, "demand.csv")}
        miss = sorted(dem_models - colors)
        add("规则", "颜色换型时每个车型都有颜色", "FAIL" if miss else "PASS", f"缺颜色 {miss}" if miss else "")
    cq = float(g.get("co2_per_unit", 0) or 0)
    if cq and float(g.get("carbon_price", 0) or 0) > 0 and float(g.get("carbon_cost_per_unit", 0) or 0) > 0:
        add("规则", "碳配额与碳单价成对启用", "FAIL", "co2_per_unit/carbon_price 已启用，carbon_cost_per_unit 应置 0 避免重复计")
    else:
        add("规则", "碳配额与碳单价成对启用", "PASS", "")
    return plant, res

def readiness(res):
    """就绪度（示例口径 ⚠）：L0 缺核心文件；L1 结构齐；L2 完整性+规则通过；L3 有实际数据可回测"""
    f = lambda cats: all(r[2] != "FAIL" for r in res if r[0] in cats)
    if not f({"结构"}): return "L0 未就绪：核心参数表不齐"
    if not f({"版本", "完整性", "规则"}): return "L1 结构就绪：参数表齐，但有缺口或规则不通过"
    if not any(r[1] == "actual.csv" and r[2] == "PASS" for r in res): return "L2 可测算：可以跑模型，但缺实际数据，不能回测对账"
    return "L3 可回测：可以跑模型并做历史回测对账"

def main(base):
    plant, res = check(base); lv = readiness(res); pid = plant.get("plant_id", os.path.basename(base))
    lines = [f"# 工厂配置包检查：{pid}（{plant.get('plant_name','')}）", "", f"- 配置包：`{os.path.relpath(base, HERE)}`",
             f"- 核心版本：{plant.get('core_version')}　配置版本：{plant.get('config_version')}", f"- **就绪度：{lv}**", "",
             "| 类别 | 检查项 | 结果 | 说明 |", "|:--|:--|:--|:--|"] + [f"| {c} | {i} | {ok} | {m} |" for c, i, ok, m in res]
    os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
    open(os.path.join(HERE, "output", f"readiness_{pid}.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines)); return lv

if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "data"))
