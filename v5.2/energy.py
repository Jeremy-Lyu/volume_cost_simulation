"""v5.1 能源层：浙江分时电价（TOU）+ 运行/待机/天然气/启停炉/需量电费
数据（缺文件或 tou_enabled=false = 退回 v5 单一电价口径）：
  data/tou_periods.csv   版本×季节×小时段 → 尖峰/高峰/平段/低谷
  data/tou_price.csv     版本×季节×时段 → 110kV / 10kV 代理购电价（元/kWh）
  data/shift_times.csv   早/中/夜/加班 的起止时刻，及 1/2/3 班各用哪几个班
  data/shop_energy.csv   车间待机比例、燃气、启炉能耗、电泳保温、周末/夜间策略（hold/shutdown/auto）
  data/energy_config.json 版本(2026/2024)、电压、购电方式、需量电价、气价、同时率
全部数字为示例/⚠ 暂定，需用工厂电表、气表与合同校准。"""
import csv, json, os, calendar

def _rows(base, n):
    p = os.path.join(base, n)
    if not os.path.exists(p): return []
    with open(p, encoding="utf-8") as f: return list(csv.DictReader(f))

def load(base, d):
    """读能源配置；没有 tou 文件或关闭开关 → d['tou'] = None（v5 口径）"""
    cp = os.path.join(base, "energy_config.json")
    cfg = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else {}
    per, pri = _rows(base, "tou_periods.csv"), _rows(base, "tou_price.csv")
    d["ecfg"] = cfg
    if not (per and pri and cfg.get("tou_enabled", True)):
        d["tou"] = None; return
    hours, season = {}, {}
    for r in per:
        for m in r["months"].split("|"):
            key = (r["version"], int(m)); season[key] = r["season"]
            arr = hours.setdefault(key, [None] * 24)
            for h in range(int(r["hour_start"]), int(r["hour_end"])): arr[h] = r["period"]
    price = {(r["version"], r["season"], r["period"]): {"110kV": float(r["price_110kV"]), "10kV": float(r["price_10kV"])} for r in pri}
    d["tou"] = dict(hours=hours, season=season, price=price)
    st = _rows(base, "shift_times.csv")
    d["shift_times"] = {r["shift"]: dict(start=int(r["start"]), end=int(r["end"]), used=r["used_by_shifts"].split("|")) for r in st}
    d["shop_e"] = {r["shop"]: {k: (v if k in ("weekend_policy", "night_policy", "note") else float(v)) for k, v in r.items() if k != "shop"}
                   for r in _rows(base, "shop_energy.csv")}
    d["g"].setdefault("elec_price_base", d["g"]["elec_price"])   # 场景"电价×系数"= elec_price / elec_price_base
    d["g"].setdefault("gas_price", float(cfg.get("gas_price", 3.6)))
    d["g"].setdefault("demand_charge_kw_month", float(cfg.get("demand_charge_kw_month", 40.8)))

def active(d): return bool(d.get("tou"))
def version(d): return str(d.get("ecfg", {}).get("tou_version", "2026"))
def elec_factor(d):
    f = d["g"]["elec_price"] / d["g"].get("elec_price_base", d["g"]["elec_price"])
    if d["ecfg"].get("purchase_mode", "agent") == "market": f *= float(d["ecfg"].get("market_price_factor", 1.0))
    return f

def hour_prices(d, t):
    """月份 t 的 24 小时电价（元/kWh），含电价场景系数"""
    v = version(d); tt = t if t else 10
    per = d["tou"]["hours"][(v, tt)]; se = d["tou"]["season"][(v, tt)]; vol = d["ecfg"].get("voltage", "110kV")
    f = elec_factor(d) * d.get("elec_month_factor", {}).get(t, 1.0)
    return [d["tou"]["price"][(v, se, p)][vol] * f for p in per]

def _span(a, b): return list(range(a, b)) if b > a else list(range(a, 24)) + list(range(0, b))
def shift_hours(d, k):
    """k 班对应的小时集合（按 shift_times.csv 的 used_by_shifts）"""
    hs = []
    for nm, r in d["shift_times"].items():
        if str(k) in r["used"]: hs += _span(r["start"], r["end"])
    return sorted(set(hs))

def _avg(p, hs): return sum(p[h] for h in hs) / len(hs) if hs else 0.0
def shift_price(d, t, k):      # 班次加权电价：在开的各班小时的平均价
    p = hour_prices(d, t); return _avg(p, shift_hours(d, k) if k else range(24))
def off_price(d, t, k):        # 不开班时段的平均价（夜间/班间）
    p = hour_prices(d, t); hs = set(shift_hours(d, k)); return _avg(p, [h for h in range(24) if h not in hs])
def day_price(d, t): return _avg(hour_prices(d, t), range(24))
def ot_price(d, t):            # 加班按其所在时段计价（默认休息日 8–16）
    r = d["shift_times"].get("加班", dict(start=8, end=16)); return _avg(hour_prices(d, t), _span(r["start"], r["end"]))
def heatup_price(d, t, hrs):   # 升温时段 = 开班前 hrs 小时
    end = int(d["ecfg"].get("heatup_window_end", 8)); return _avg(hour_prices(d, t), _span((end - int(round(hrs or 1))) % 24, end))
def gas(d): return d["g"]["gas_price"]
def caldays(d, t): return calendar.monthrange(int(d["ecfg"].get("year", 2026)), t)[1] if t else 30

def se(d, s): return d.get("shop_e", {}).get(s, dict(standby_kw_ratio=0.0, off_kw_ratio=0.0, gas_run_m3h=0.0, gas_m3_per_unit=0.0, gas_standby_ratio=0.0,
                                                      heatup_hours=0.0, heatup_kwh=0.0, heatup_m3=0.0, ecoat_hold_kw=0.0, ecoat_hold_m3h=0.0,
                                                      weekend_policy="hold", night_policy="hold"))
def hold_cost_h(d, s, kw, p):  # 保温/待机每小时：待机电 + 保温气
    e = se(d, s); return e["standby_kw_ratio"] * kw * p + e["gas_run_m3h"] * e["gas_standby_ratio"] * gas(d)
def off_cost_h(d, s, kw, p):   # 停炉每小时：基础负荷 + 电泳槽保温（不停热）
    e = se(d, s); return (e["off_kw_ratio"] * kw + e["ecoat_hold_kw"]) * p + e["ecoat_hold_m3h"] * gas(d)
def startup_cost(d, s, t):     # 一次启炉（只含烘房+喷房；电泳不停热，不计）
    e = se(d, s); return e["heatup_kwh"] * heatup_price(d, t, e["heatup_hours"]) + e["heatup_m3"] * gas(d)
def breakeven_hours(d, s, kw, t, p=None):   # 停机间隔超过此值就停炉更省
    p = day_price(d, t) if p is None else p
    dh = hold_cost_h(d, s, kw, p) - off_cost_h(d, s, kw, p)
    return startup_cost(d, s, t) / dh if dh > 0 else float("inf")

def _gap(d, s, kw, t, hours_gap, n_gaps, p, policy):
    """一类停机间隔（周末/夜间）的能源：返回 (待机电, 气, 启停, 选择)"""
    e = se(d, s)
    hold = dict(el=e["standby_kw_ratio"] * kw * p * hours_gap * n_gaps, gas=e["gas_run_m3h"] * e["gas_standby_ratio"] * gas(d) * hours_gap * n_gaps, st=0.0)
    off = dict(el=(e["off_kw_ratio"] * kw + e["ecoat_hold_kw"]) * p * hours_gap * n_gaps, gas=e["ecoat_hold_m3h"] * gas(d) * hours_gap * n_gaps,
               st=startup_cost(d, s, t) * n_gaps)
    if policy == "auto": policy = "shutdown" if sum(off.values()) < sum(hold.values()) else "hold"
    c = off if policy == "shutdown" else hold
    return c["el"], c["gas"], c["st"], ("停炉" if policy == "shutdown" else "保温")

def parts(d, s, o, k, t, run_h, workdays):
    """月度固定能源分项（k≥1）。run_h=有效开动小时；workdays=开工天数"""
    kw, e = o["kw"], se(d, s)
    sp = shift_price(d, t, k)
    run_el = kw * run_h * sp
    idle_in_shift = max(len(shift_hours(d, k)) * workdays - run_h, 0.0)      # 班内非开动时间（休息/换型）按待机
    el_sb = e["standby_kw_ratio"] * kw * idle_in_shift * sp
    g = e["gas_run_m3h"] * run_h * gas(d) + e["gas_run_m3h"] * e["gas_standby_ratio"] * idle_in_shift * gas(d)
    st = 0.0; pol = {}
    nh = 24 - len(shift_hours(d, k))
    if nh > 0 and workdays > 0:                                               # 夜间/班间
        a, b, c, pol["夜间"] = _gap(d, s, kw, t, nh, workdays, off_price(d, t, k), e["night_policy"]); el_sb += a; g += b; st += c
    rest = max(caldays(d, t) - workdays, 0.0)
    if rest > 0:                                                              # 休息日：按 2 天一段 ⚠
        blocks = max(rest / 2.0, 1.0)
        a, b, c, pol["周末"] = _gap(d, s, kw, t, 24 * rest / blocks, blocks, day_price(d, t), e["weekend_policy"]); el_sb += a; g += b; st += c
    dem = float(d["ecfg"].get("demand_coincidence", 0.85)) * kw * d["g"]["demand_charge_kw_month"]
    r = {"能源-电(运行)": run_el, "能源-电(待机)": el_sb, "能源-天然气": g, "启停能耗": st, "需量电费": dem}
    return {kk: vv for kk, vv in r.items() if vv}, pol

def estimate_per_unit(d, s, o, k, t, volume, workdays=21, rate=0.9):
    """调整 JPH 时估算单车能源（元/台）：开线小时 = 产量 ÷ (JPH × 开动率)；其余时间按待机/保温，周末按策略。
    返回 dict（运行电/待机电/天然气/启停/单车变动/合计，元/台）。不进优化，供快速估算与测试。"""
    run_h = volume / (o["jph"] * rate)
    p, pol = parts(d, s, o, k, t, run_h, workdays)
    p.pop("需量电费", None)
    p["单车变动"] = (d["shop"][s]["kwh_per_unit"] * shift_price(d, t, k) + se(d, s)["gas_m3_per_unit"] * gas(d)) * volume
    r = {kk: vv / volume for kk, vv in p.items()}; r["合计"] = sum(r.values()); return r
