"""块1-6：主数据/参数/需求/产能/JPH档/日历班次 —— 读取参数表"""
import csv, os, copy, json
DATA = os.path.join(os.path.dirname(__file__), "data")
SHOPS = ["STP", "BIW", "PNT", "TCF"]   # 默认车间链：冲压→焊装→涂装→总装（data/plant.json 可覆盖）

def load(data_dir=None):
    """data_dir=工厂配置包目录（默认 data/ = 示例配置包）。plant.json 定义工厂ID、车间链、版本；没有就用默认车间链。
    多工厂复制：换一个配置包目录即可，核心代码不改（第 21 节）。"""
    base = data_dir or DATA
    def _r(n):
        with open(os.path.join(base, n), encoding="utf-8") as f: return list(csv.DictReader(f))
    pj = os.path.join(base, "plant.json")
    plant = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else {"plant_id": "DEFAULT", "shops": SHOPS}
    d = {"shops": list(plant["shops"]), "plant": plant}
    d["demand"] = {(int(r["month"]), r["model"]): float(r["demand"]) for r in _r("demand.csv")}
    d["months"] = sorted({t for t, _ in d["demand"]}); d["models"] = sorted({m for _, m in d["demand"]})
    d["days"] = {int(r["month"]): float(r["workdays"]) for r in _r("calendar.csv")}
    d["cap"] = {(r["shop"], r["model"], int(r["month"])): float(r["cap"]) for r in _r("capacity_limit.csv")}
    d["jph"] = {}
    for r in _r("jph_options.csv"):
        d["jph"].setdefault(r["shop"], []).append({"jph": float(r["jph"]), "heads": float(r["heads_per_shift"]), "kw": float(r["run_kw"]),
                                                "mix_eff": float(r.get("mix_eff") or 1.0)})   # A07：车型混线有效系数，缺列 = 1
    d["shift"] = {int(r["shifts"]): {k: float(v) for k, v in r.items()} for r in _r("shift_options.csv")}
    d["shop"] = {r["shop"]: {k: float(v) for k, v in r.items() if k != "shop"} for r in _r("shop_params.csv")}
    d["g"] = {r["key"]: float(r["value"]) for r in _r("global_params.csv")}
    for key, default in (("burden_rate", 1.0), ("capital_rate_month", 0.0),
                         ("warranty_per_unit", 0.0), ("carbon_cost_per_unit", 0.0),
                         ("fg_hold_cost_per_unit_month", 0.0), ("co2_per_unit", 0.0),
                         ("carbon_free_quota_month", 0.0), ("carbon_price", 0.0)):
        d["g"].setdefault(key, default)
    # v4 新参数（缺省 = 示例值，⚠ 暂定）
    for key, default in (("std_hours_month", 174.0), ("ot_multiplier", 1.5), ("ot_hard_cap_per_head_month", 60.0),
                         ("ot_excess_premium_per_head_hour", 30.0), ("night_allowance_per_head_night", 30.0),
                         ("backlog_cost_per_unit_month", 1500.0)):
        d["g"].setdefault(key, default)
    d["g"].pop("ot_rate_per_head_hour", None)        # v4 规则5：加班单价改为派生，不再读固定值
    NS = {0: 0.0, 1: 0.0, 2: 1.0, 3: 1.0}
    for k, row in d["shift"].items(): row.setdefault("night_shifts", NS.get(k, 1.0))
    d["shift"].setdefault(0, {"shifts": 0.0, "eff_hours_per_shift": 0.0, "night_shifts": 0.0,
                              "bus_cost_per_shift_month": 0.0, "outsourcing_per_shift_month": 0.0})   # v4 规则3：0 班
    for s in d["shop"]: d["shop"][s].setdefault("idle_fixed_month", 300000.0)
    for s in d["jph"]: d["jph"][s].sort(key=lambda o: o["jph"])              # jph_step 依赖升序
    _optional(base, d)
    import energy; energy.load(base, d)          # v5.1：分时电价与能源分项（缺文件 = v5 口径）
    validate(d); return d

def _optional(base, d):
    """可选扩展参数表（v2）：缺文件 = 不启用，口径与基础版一致。
    mat_cost.csv 物料单车成本 | quality.csv 一次合格率 FTT | ramp.csv 爬坡系数
    shipping_cap.csv 发运能力上限 | indirect.csv 间接人员定员 | changeover.csv 换型换色
    month=0 表示该车型/月份的默认值"""
    def _o(n):
        p = os.path.join(base, n)
        if not os.path.exists(p): return []
        with open(p, encoding="utf-8") as f: return list(csv.DictReader(f))
    d["mat"] = {(r["model"], int(r["month"])): float(r["cost_per_unit"]) for r in _o("mat_cost.csv")}
    d["qual"] = {r["shop"]: float(r["ftt"]) for r in _o("quality.csv")}
    d["ramp"] = {(r["shop"], int(r["month"])): float(r["factor"]) for r in _o("ramp.csv")}
    d["ship"] = {(r["model"], int(r["month"])): float(r["cap"]) for r in _o("shipping_cap.csv")}
    d["indirect"] = {}
    for r in _o("indirect.csv"): d["indirect"].setdefault(r["shop"], {})[float(r["jph"])] = float(r["heads_per_shift"])
    d["chg"] = {r["shop"]: {**{k: (float(v) if str(v).strip() else 0.0) for k, v in r.items() if k not in ("shop", "mode")},
                            "mode": (r.get("mode") or "fixed")} for r in _o("changeover.csv")}
    d["carrier"] = {r["shop"]: float(r["carriers"]) for r in _o("carrier.csv")}          # 滑橇/吊具数量 → 有效缓存上限
    d["lanes"] = [{"lane": r["lane"], "mode": r["mode"], "capacity": float(r["capacity"]),
                   "cost_per_trip": float(r["cost_per_trip"]),
                   "fixed_month_cost": float(r.get("fixed_month_cost") or 0),
                   "scope": (r.get("scope") or "outbound")} for r in _o("logistics.csv")]
    d["tool"] = {(r["model"], int(r["month"])): float(r["monthly_amount"]) for r in _o("tooling.csv")}
    d["dep"] = {r["shop"]: float(r["monthly_depreciation"]) for r in _o("asset.csv")}
    d["margin"] = {(r["model"], int(r["month"])): float(r["margin_per_unit"]) for r in _o("margin.csv")}
    d["oee"] = {(r["shop"], int(r["month"])): {"time_rate": float(r["time_rate"]), "perf_rate": float(r["perf_rate"])}
                for r in _o("oee.csv")}                                    # OEE 时间开动率 × 性能开动率
    d["att"] = {(r["shop"], int(r["month"])): float(r["rate"]) for r in _o("attendance.csv")}   # 出勤率（单列）
    d["avail_file"] = {(r["shop"], int(r["month"])): float(r["rate"]) for r in _o("avail.csv")} # 静态限产/开动率（环保限产等）
    d["rework"] = {r["shop"]: {k: float(v) for k, v in r.items() if k != "shop"} for r in _o("rework.csv")}  # 返修区
    d["line_supply"] = {}
    for r in _o("line_supply.csv"):   # 叫料上限、在途到货、安全缓冲、期初循环库存、报废与冲销
        d["line_supply"][(r["model"], int(r["month"]))] = {
            "calloff_cap": float(r["calloff_cap"]),
            "git_incoming": float(r.get("git_incoming") or 0),
            "safety_buffer": float(r.get("safety_buffer") or 0),
            "opening_stock": float(r.get("opening_stock") or 0),
            "scrap_rate": float(r.get("scrap_rate") or 0),
            "cancel_rate": float(r.get("cancel_rate") or 0)}
    d["color"] = {r["model"]: r["color"] for r in _o("models.csv") if r.get("color")}
    d["color_batch"] = {r["color"]: float(r["batch"]) for r in _o("color_batch.csv")}
    groups = {}
    for r in _o("capacity_component.csv"):   # 同一车型同一月，各厂上限取最小（能力分量交集）
        groups.setdefault((r["model"], int(r["month"])), []).append(float(r["max_orders"]))
    d["cap_component"] = {k: min(v) for k, v in groups.items()}
    d["part_price"] = {}
    d["part_currency"] = {}
    for r in _o("part_price.csv"):   # 零件价 × 汇率 = 人民币物料；月份即生效区间（模型粒度为月）
        k = (r["model"], int(r["month"]))
        d["part_price"][k] = float(r["price"]) * float(r["fx_rate"])
        d["part_currency"][k] = r.get("currency") or "CNY"
    # v5.2：按天人工弹性（缺文件 = 不启用）与 JPH 换档成本
    d["lflex"] = {r["shop"]: {k: float(v) for k, v in r.items() if k not in ("shop", "note")} for r in _o("labor_flex.csv")}
    d["jsw"] = {r["shop"]: {k: float(v) for k, v in r.items() if k not in ("shop", "note")} for r in _o("jph_switch.csv")}
    d["slot_cap"] = {(r["model"], int(r["month"])): float(r["cap"]) for r in _o("slot_cap.csv")}
    d["coarse"] = _coarse(_o("coarse_params.csv"))

def _coarse(rows):
    """六个粗参数。空的人数上下限 = 不限制；其余默认不改变现成本。"""
    spec = {"head_up": None, "head_dn": None, "post_switch_eff": 1.0, "pm_days": 0.0, "moq_fee": 0.0, "restart_cost": 0.0}
    for r in rows:
        key = (r.get("key") or "").strip()
        if key not in spec:
            continue
        raw = (r.get("value") or "").strip()
        spec[key] = float(raw) if raw else spec[key]
    return spec

def validate(d):
    """参数校验（块2 验收）：完整性与范围"""
    for t in d["months"]:
        assert t in d["days"], f"缺日历 {t}"
        for m in d["models"]:
            for s in d["shops"]: assert (s, m, t) in d["cap"], f"缺产能上限 {s},{m},{t}"
    for s in d["shops"]: assert d["jph"].get(s), f"{s} 无JPH档"
    for t in d["months"]: assert d["days"][t] > 0, f"{t} 月工作日≤0"
    for s in d["shops"]:
        js = d["jph"][s]
        for a, b in zip(js, js[1:]): assert b["heads"] >= a["heads"], f"{s} 定员未随 JPH 单调"
        assert d["shop"][s]["ot_max_hours_month"] <= d["g"]["ot_hard_cap_per_head_month"], f"{s} 加班常规上限>绝对上限"

def set_ot_cap(d, h):          # 场景/策略"加班上限"旋钮：常规与绝对上限都设为 h（严格上限）
    for s in d["shop"]: d["shop"][s]["ot_max_hours_month"] = h
    d["g"]["ot_hard_cap_per_head_month"] = h

def scenario(d, demand=1.0, elec=1.0, wage=1.0):
    e = copy.deepcopy(d)
    e["demand"] = {k: v * demand for k, v in e["demand"].items()}
    e["g"]["elec_price"] *= elec; e["g"]["wage_per_head_month"] *= wage   # 加班单价由工资派生，自动联动；v5.1 分时电价按 elec_price/elec_price_base 等比缩放
    return e
