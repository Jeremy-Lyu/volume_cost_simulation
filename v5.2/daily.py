"""v5.1 按天排产层：焊装 → 白车身缓存 → 涂装 → PBS（涂装后缓存）→ 总装（示例数据）
决策（每车间每天）：开/不开（二进制）、开几班、月度 JPH 档与定员班次数；不开时 保温 还是 停炉（off）；停炉后再开计一次启炉成本
约束：白车身缓存日平衡 B[d]=B[d-1]+焊装产出−涂装投入，下限 ≤ B ≤ 库容；PBS 同理供总装（总装按工作日均衡拉动）；月末缓存不低于月初
成本：人工（定员班次月薪 + 夜班补贴 + 休息日加班费）+ 班车外包 + 分时能源（运行电/待机电/天然气/启停/需量）+ 缓存持有与资金占用 + 缺货惩罚
策略：continuous=工作日三班连续、周末保温；sync=焊装与涂装同开同停（模型选哪天开）；optimal=模型自由排；two_shift=工作日两班+周末停炉（参考）
参数：data/daily_config.json + 能源参数（energy_config.json / shop_energy.csv / tou_*.csv），全部 ⚠ 暂定
用法：python3 daily.py [--strategies=continuous,sync,optimal,two_shift] [--no-cache]"""
import copy, csv, json, os, sys, time, hashlib, pickle
import pulp
import data_loader as dl, cost_functions as cf, energy as E, solve_meta
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "output", "v5.1"); CACHE = os.path.join(H, ".cache")
NAMES = dict(continuous="连续生产（工作日三班、周末保温）", sync="焊装涂装同步开停（模型选日）", optimal="模型自主排产", two_shift="工作日两班+周末停炉（参考）", weekdays="每个工作日都开（不主动停线，对照）")

def load_cfg(base=None):
    return json.load(open(os.path.join(base or dl.DATA, "daily_config.json"), encoding="utf-8"))

def day_terms(d, cfg, s, o, k, t):
    """某车间某天按 (JPH档 o, k 班) 开工的固定能源（元/天）与产能（台/天）"""
    e = E.se(d, s); kw = o["kw"]; nh = len(E.shift_hours(d, k)); effh = d["shift"][k]["eff_hours_per_shift"] * k
    sp = E.shift_price(d, t, k); g = E.gas(d)
    run = kw * effh * sp
    idle = max(nh - effh, 0); sb = e["standby_kw_ratio"] * kw * idle * sp
    gas = e["gas_run_m3h"] * effh * g + e["gas_run_m3h"] * e["gas_standby_ratio"] * idle * g
    gap = 24 - nh
    if gap > 0:   # 班间/夜间：按 night_policy（hold=保温；auto=按临界间隔）
        a, b, c, _ = E._gap(d, s, kw, t, gap, 1, E.off_price(d, t, k), e["night_policy"]); sb += a; gas += b; run += c
    return dict(el_run=run, el_sb=sb, gas=gas), o["jph"] * o.get("mix_eff", 1.0) * effh * cfg["daily_capacity_factor"]

def pm_days(cfg):
    """A08：PM 日历 → 本月的日序号（0 起）。接受 "MM-DD"、"YYYY-MM-DD" 或整数日；不在本月的忽略（不核对年份）"""
    out = set()
    for x in cfg.get("pm_dates") or []:
        if isinstance(x, int): m, dd = cfg["month"], x
        else: p = str(x).split("-"); m, dd = int(p[-2]), int(p[-1])
        if m == cfg["month"] and 1 <= dd <= cfg["days"]: out.add(dd - 1)
    return out

def build(d, cfg, strategy="optimal", buf_max=None, fix=None):
    t = cfg["month"]; D = range(cfg["days"]); S = cfg["shops"]; K = [k for k in sorted(d["shift"]) if k > 0]
    wk = [(cfg["first_weekday"] + i) % 7 >= 5 for i in D]; pmd = pm_days(cfg)   # A08：PM 日全厂停线，总装需求摊到其余工作日
    nwd = sum(1 for i in D if not wk[i] and i not in pmd)
    need = [0 if (wk[i] or i in pmd) else cfg["monthly_demand"] / nwd for i in D]
    g = d["g"]; wage = g["wage_per_head_month"] * g.get("burden_rate", 1.0); hr = g["wage_per_head_month"] / g["std_hours_month"]
    P = pulp.LpProblem("daily", pulp.LpMinimize); acc = {}; lost_switch = []
    def add(k_, e_): acc.setdefault(k_, []).append(e_)
    I = {s: range(len(d["jph"][s])) for s in S}
    crew = {(s, i, kk): pulp.LpVariable(f"crew_{s}_{i}_{kk}", cat="Binary") for s in S for i in I[s] for kk in K}
    y = {(s, j, i, k): pulp.LpVariable(f"y_{s}_{j}_{i}_{k}", cat="Binary") for s in S for j in D for i in I[s] for k in K}
    off = {(s, j): pulp.LpVariable(f"off_{s}_{j}", cat="Binary") for s in S for j in D}
    st = {(s, j): pulp.LpVariable(f"st_{s}_{j}", lowBound=0) for s in S for j in D}
    q = {(s, j): pulp.LpVariable(f"q_{s}_{j}", lowBound=0) for s in S for j in D}
    ev = {(s, j): pulp.LpVariable(f"ev_{s}_{j}", lowBound=0) for s in S for j in D}
    B = {j: pulp.LpVariable(f"B_{j}", lowBound=cfg["biw_buffer_min"]) for j in D}
    PB = {j: pulp.LpVariable(f"PB_{j}", lowBound=cfg["pbs_buffer_min"]) for j in D}
    sh = {j: pulp.LpVariable(f"sh_{j}", lowBound=0) for j in D}
    peak = pulp.LpVariable("peak_kw", lowBound=0)
    opn = {(s, j): pulp.lpSum(y[(s, j, i, k)] for i in I[s] for k in K) for s in S for j in D}
    caps = {}
    fvs = {s: (cfg["labor_daily_variable_share"] if cfg.get("labor_daily_variable_share") is not None else cf.flex_var_share(d, s)) for s in S}   # v5.2：按 labor_flex.csv 推出
    crewheads = {s: pulp.lpSum(crew[(s, i, kk)] * (d["jph"][s][i]["heads"] + cf.indirect_heads(d, s, d["jph"][s][i])) * kk for i in I[s] for kk in K) for s in S}
    for s in S:
        e = E.se(d, s); kw0 = d["jph"][s][0]["kw"]
        P += pulp.lpSum(crew[(s, i, kk)] for i in I[s] for kk in K) == 1, f"crew1_{s}"
        for i in I[s]:
            o = d["jph"][s][i]; heads = o["heads"] + cf.indirect_heads(d, s, o)
            for kk in K:
                add("人工", crew[(s, i, kk)] * heads * kk * wage * (1 - fvs[s]))   # 月薪固定部分（停工日也要发的）
                pt = (cfg.get("prev_jph_tier") or {}).get(s)
                if pt is not None and i != pt and cf.jph_switch(d, s):   # v5.2：与上月 JPH 档不同 → 换档成本 + 损失产出（按损失天数×日产能计惩罚）
                    js = cf.jph_switch(d, s)
                    add("JPH换档", crew[(s, i, kk)] * js["cost_per_switch"])
                    lost_switch.append((s, crew[(s, i, kk)] * (js["lost_days"] + (cfg.get("learning_extra_lost_days") or 0)) * o["jph"] * o.get("mix_eff", 1.0) * d["shift"][kk]["eff_hours_per_shift"] * kk * cfg["daily_capacity_factor"]))
                add("班车外包", crew[(s, i, kk)] * (d["shift"][kk]["bus_cost_per_shift_month"] + d["shift"][kk]["outsourcing_per_shift_month"]) * kk)
        for j in D:
            P += opn[(s, j)] <= 1, f"open1_{s}_{j}"
            P += off[(s, j)] <= 1 - opn[(s, j)], f"offc_{s}_{j}"
            P += st[(s, j)] >= (off[(s, j - 1)] if j else 0) - off[(s, j)], f"start_{s}_{j}"
            capj = []
            for i in I[s]:
                o = d["jph"][s][i]; heads = o["heads"] + cf.indirect_heads(d, s, o)
                for k in K:
                    P += y[(s, j, i, k)] <= pulp.lpSum(crew[(s, i, kk)] for kk in K if kk >= k), f"crewlink_{s}_{j}_{i}_{k}"
                    tm, cp = day_terms(d, cfg, s, o, k, t); caps[(s, i, k)] = cp; capj.append(cp * y[(s, j, i, k)])
                    add("能源-电(运行)", tm["el_run"] * y[(s, j, i, k)]); add("能源-电(待机)", tm["el_sb"] * y[(s, j, i, k)]); add("能源-天然气", tm["gas"] * y[(s, j, i, k)])
                    add("人工", y[(s, j, i, k)] * heads * cf.night_shifts(d, k) * g["night_allowance_per_head_night"])
                    if fvs[s] and not wk[j]:   # ⚠ 可按天省的人工（派遣 + 正式工停工日少发部分）：只在开工的工作日计
                        add("人工", y[(s, j, i, k)] * heads * k * wage / cf.paid_days(d, s) * fvs[s])
                    if wk[j]: add("休息日加班费", y[(s, j, i, k)] * heads * k * 8 * hr * cfg["weekend_ot_multiplier"])
            P += q[(s, j)] <= pulp.lpSum(capj), f"cap_{s}_{j}"
            for k in K:   # 单车电耗 × 所选班次加权电价（线性化）
                c = d["shop"][s]["kwh_per_unit"] * E.shift_price(d, t, k)
                P += ev[(s, j)] >= c * q[(s, j)] - c * 3000 * (1 - pulp.lpSum(y[(s, j, i, k)] for i in I[s])), f"ev_{s}_{j}_{k}"
            add("能源变动", ev[(s, j)] + cf.var_gas(d, s) * q[(s, j)])
            add("能源-电(待机)", (1 - opn[(s, j)] - off[(s, j)]) * 24 * e["standby_kw_ratio"] * kw0 * E.day_price(d, t)
                + off[(s, j)] * 24 * (e["off_kw_ratio"] * kw0 + e["ecoat_hold_kw"]) * E.day_price(d, t))
            add("能源-天然气", (1 - opn[(s, j)] - off[(s, j)]) * 24 * e["gas_run_m3h"] * e["gas_standby_ratio"] * E.gas(d) + off[(s, j)] * 24 * e["ecoat_hold_m3h"] * E.gas(d))
            add("启停能耗", st[(s, j)] * E.startup_cost(d, s, t))
            if wk[j] and not cfg.get("allow_weekend_work", True): P += opn[(s, j)] == 0, f"nowe_{s}_{j}"
    # v5.2：跨车间借调。借入方少雇 bw 人；开工日要用 u 人，来源 = 另一车间当天空闲的人（停线或少开班）
    bwv = {}
    if cfg.get("allow_borrow", True) and len(S) == 2 and all(cf.lflex(d, s) for s in S):
        for s in S:
            ot_ = S[1] if s == S[0] else S[0]
            bwv[s] = pulp.LpVariable(f"bw_{s}", lowBound=0); P += bwv[s] <= cf.lflex(d, s)["borrow_limit"] * crewheads[s], f"bwl_{s}"
            add("借调节省人工", -bwv[s] * wage)
            M = 2000
            for j in D:
                u = pulp.LpVariable(f"u_{s}_{j}", lowBound=0)
                P += u >= bwv[s] - M * (1 - opn[(s, j)]), f"bwu_{s}_{j}"
                idle = crewheads[ot_] - pulp.lpSum(y[(ot_, j, i, k)] * (d["jph"][ot_][i]["heads"] + cf.indirect_heads(d, ot_, d["jph"][ot_][i])) * k for i in I[ot_] for k in K)
                P += u <= idle, f"bwsrc_{s}_{j}"
                if not wk[j]: add("借调占用(借出方停工日不能省)", u * wage / cf.paid_days(d, ot_) * fvs[ot_])
    for j in D:
        P += peak >= float(d["ecfg"].get("demand_coincidence", 0.85)) * pulp.lpSum(d["jph"][s][i]["kw"] * y[(s, j, i, k)] for s in S for i in I[s] for k in K), f"peak_{j}"
    add("需量电费", peak * d["g"]["demand_charge_kw_month"])
    bmax = cfg["biw_buffer_max"] if buf_max is None else buf_max
    a, b = S[0], S[1]
    for j in D:
        P += B[j] == (B[j - 1] if j else cfg["biw_buffer_start"]) + q[(a, j)] - q[(b, j)], f"bal_{j}"
        P += B[j] <= bmax, f"bufmax_{j}"
        P += PB[j] == (PB[j - 1] if j else cfg["pbs_buffer_start"]) + q[(b, j)] + sh[j] - need[j], f"pbs_{j}"
        P += PB[j] <= cfg["pbs_buffer_max"], f"pbsmax_{j}"
        add("缓存持有", B[j] * (cfg["hold_cost_per_unit_day"] + cfg["body_value_biw"] * cfg["capital_rate_month"] / 30)
            + PB[j] * (cfg["hold_cost_per_unit_day"] + cfg["body_value_pbs"] * cfg["capital_rate_month"] / 30))
        add("缺货惩罚", sh[j] * cfg["shortage_penalty_per_unit"])
    for s in S:   # 换档损失产出：从当月可用产能里扣（作为月末必须多生产的量）
        ls = [e_ for s_, e_ in lost_switch if s_ == s]
        if ls: P += pulp.lpSum(q[(s, j)] for j in D) <= pulp.lpSum(caps[(s, i, k)] * y[(s, j, i, k)] for j in D for i in I[s] for k in K) - pulp.lpSum(ls), f"swlost_{s}"
    P += B[D[-1]] >= cfg["biw_buffer_start"], "bufend"; P += PB[D[-1]] >= cfg["pbs_buffer_start"], "pbsend"
    if strategy == "continuous":
        for s in S:
            for j in D:
                if wk[j]: P += opn[(s, j)] == 0, f"cw_{s}_{j}"; P += off[(s, j)] == 0, f"ch_{s}_{j}"
                elif j not in pmd: P += pulp.lpSum(y[(s, j, i, 3)] for i in I[s]) == 1, f"c3_{s}_{j}"
    elif strategy == "two_shift":
        for s in S:
            for j in D:
                if wk[j]: P += opn[(s, j)] == 0, f"tw_{s}_{j}"; P += off[(s, j)] == 1, f"to_{s}_{j}"
                elif j not in pmd: P += pulp.lpSum(y[(s, j, i, 2)] for i in I[s]) == 1, f"t2_{s}_{j}"
    elif strategy == "weekdays":   # v5.2 对照：每个工作日都开（班次可选），不主动停线
        for s in S:
            for j in D:
                if not wk[j] and j not in pmd: P += opn[(s, j)] == 1, f"wd_{s}_{j}"
    elif strategy == "sync":
        for j in D:
            for k in K: P += pulp.lpSum(y[(a, j, i, k)] for i in I[a]) == pulp.lpSum(y[(b, j, i, k)] for i in I[b]), f"sync_{j}_{k}"
    if cfg.get("same_shift_as_crew"):   # v5.2 敏感性：开工日必须开满定员班次的班数（不能"每天少开一班"），只能整天停
        for s in S:
            for j in D:
                for i in I[s]:
                    for k in K: P += y[(s, j, i, k)] <= crew[(s, i, k)], f"ssc_{s}_{j}_{i}_{k}"
    for s, kk0 in (cfg.get("fix_crew") or {}).items():   # v5.2：定员班次按月已定（例如沿用上月 2 班定员），当月只能靠开停天数调节
        P += pulp.lpSum(crew[(s, i, kk)] for i in I[s] for kk in K if kk == kk0) == 1, f"fixcrew_{s}"
    # ===== A05–A10 按天层参数（默认全部关闭：不建任何变量和约束，结果与关闭前逐格一致；数值均为 ⚠ 示例） =====
    for j in sorted(pmd):   # A08 计划维修：PM 日焊装、涂装都不开（计入停线天数）
        for s in S: P += opn[(s, j)] == 0, f"pm_{s}_{j}"
    if (cfg.get("hire_lead_months") or 0) >= 1 and cfg.get("prev_crew"):   # A05 招聘提前期 ≥ 1 月：本月定员人数不能超过上月（可减不可加）
        for s, (pj, pk) in cfg["prev_crew"].items():
            if s not in S: continue
            po = next(o_ for o_ in d["jph"][s] if o_["jph"] == float(pj))
            P += crewheads[s] <= (po["heads"] + cf.indirect_heads(d, s, po)) * pk + 1e-6, f"hirelead_{s}"
    rq = float(cfg.get("restart_quality_cost") or 0)
    if rq > 0:   # A10 复产质量：每次启线（前一天不开、当天开）计一笔质量损失；月初第 1 天不计
        for s in S:
            for j in list(D)[1:]:
                r_ = pulp.LpVariable(f"rq_{s}_{j}", lowBound=0); P += r_ >= opn[(s, j)] - opn[(s, j - 1)], f"rq_{s}_{j}"
                add("复产质量", r_ * rq)
    jp = float(cfg.get("jit_swing_penalty_per_unit") or 0)
    if jp > 0:   # A09 MOQ/JIT：焊装相邻两个工作日产量差超过免费带宽的部分，按元/台计罚（周末与 PM 日不算，视为已提前通知）
        free = float(cfg.get("jit_free_swing_ratio") or 0) * cfg["monthly_demand"] / nwd; s0 = S[0]
        chain = [j for j in D if not wk[j] and j not in pmd]
        for a_, b_ in zip(chain, chain[1:]):
            dv = pulp.LpVariable(f"jit_{b_}", lowBound=0)
            P += dv >= q[(s0, b_)] - q[(s0, a_)] - free, f"jitu_{b_}"; P += dv >= q[(s0, a_)] - q[(s0, b_)] - free, f"jitd_{b_}"
            add("JIT波动", dv * jp)
    if fix:
        for v in P.variables():
            if v.name in fix: v.lowBound = v.upBound = fix[v.name]; v.cat = "Continuous"
    accs = {k_: pulp.lpSum(v_) for k_, v_ in acc.items()}
    P += pulp.lpSum(accs.values())
    return P, dict(acc=accs, y=y, off=off, st=st, q=q, B=B, PB=PB, sh=sh, peak=peak, crew=crew, wk=wk, need=need, caps=caps, D=D, S=S, K=K, I=I, pmd=pmd)

def integer_assignment(P):
    """求解后的整数排法。取值空着的变量不收进来。"""
    out = {}
    for var in P.variables():
        if var.cat != "Integer" or var.value() is None:
            continue
        out[var.name] = round(var.value())
    return out


def cost_fixed(d, cfg, fix, strategy="optimal", buf_max=None):
    """按给定的整数排法只算成本。不重新选班次和开停。"""
    if not fix:
        raise ValueError("没有实际排法，不能只计价。需要一张「变量,取值」表，不重新选班次。")
    P, _v = build(d, cfg, strategy, buf_max, fix=fix)
    P.solve(_solver(cfg)[0])
    return dict(status=pulp.LpStatus[P.status], obj=pulp.value(P.objective))


def load_fix(path):
    """读一张求解器变量表。文件不在时直接说明，不求解，也不编一份排法。"""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError("没有实际排法，不能做历史回放。需要一张「变量,取值」表，只计价、不重新选班次。")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or "变量" not in rows[0] or "取值" not in rows[0]:
        raise ValueError("排法表要有两列：变量,取值。")
    return {row["变量"]: round(float(row["取值"])) for row in rows if row.get("变量")}


SHOP_NAME = {"STP": "冲压", "BIW": "焊装", "PNT": "涂装", "TCF": "总装"}
SCHEDULE_COLS = ("类型", "日", "车间", "JPH", "班次", "状态")


def shop_code(name):
    name = str(name).strip()
    if name in SHOP_NAME:
        return name
    for code, label in SHOP_NAME.items():
        if name == label:
            return code
    raise ValueError(f"不认识的车间：{name}")


def _parse_state(text):
    text = str(text).strip()
    if text == "停炉":
        return None, None, "停炉"
    if text in ("保温", "保温/待机", "待机"):
        return None, None, "保温"
    if text.startswith("JPH") and "×" in text and text.endswith("班"):
        jph, shifts = text[3:-1].split("×")
        return int(jph), int(shifts), "开工"
    raise ValueError(f"状态看不懂：{text}。要用 JPH36×1班、停炉或保温。")


def _tier(d, shop, jph):
    want = int(float(jph))
    for i, opt in enumerate(d["jph"][shop]):
        if int(opt["jph"]) == want:
            return i
    raise ValueError(f"{shop} 没有 JPH {want} 这一档。")


def schedule_rows(d, result):
    """把一次求解写成计划能填的行：每个车间一条定员，每一天一条开停。"""
    rows = []
    for name, val in sorted(result["fix"].items()):
        if not str(name).startswith("crew_") or int(val) != 1:
            continue
        _tag, shop, i, kk = name.split("_")
        rows.append(dict(类型="定员", 日="", 车间=shop, JPH=int(d["jph"][shop][int(i)]["jph"]), 班次=int(kk), 状态="定员"))
    shops = [key[:-3] for key in result["sched"][0] if key.endswith("_状态")] if result["sched"] else []
    for row in result["sched"]:
        for shop in shops:
            _jph, _shifts, kind = _parse_state(row[f"{shop}_状态"])
            state = row[f"{shop}_状态"] if kind == "开工" else kind
            rows.append(dict(类型="当日", 日=row["日"], 车间=shop,
                             JPH="" if _jph is None else _jph, 班次="" if _shifts is None else _shifts, 状态=state))
    return rows


def load_schedule(path):
    """读计划填写的排法表。只有表头、或文件不在时，不求解。"""
    if not path or not os.path.isfile(path):
        raise FileNotFoundError("没有实际排法，不能做历史回放。需要一张排法表，列是类型,日,车间,JPH,班次,状态。只计价、不重新选班次。")
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("排法表是空的。要有每个车间的定员，以及每一天的开停。")
    missing = [col for col in SCHEDULE_COLS if col not in rows[0]]
    if missing:
        raise ValueError("排法表要有列：类型,日,车间,JPH,班次,状态。")
    return rows


def fix_from_schedule(d, cfg, rows):
    """排法表换成整数锁定。没写到的车间或日期不留给求解器重选。"""
    if not rows:
        raise ValueError("排法表是空的。要有每个车间的定员，以及每一天的开停。")
    shops = list(cfg["shops"])
    days = range(int(cfg["days"]))
    shifts = [k for k in sorted(d["shift"]) if k > 0]
    tiers = {s: range(len(d["jph"][s])) for s in shops}
    fix = {}
    for shop in shops:
        for i in tiers[shop]:
            for kk in shifts:
                fix[f"crew_{shop}_{i}_{kk}"] = 0
        for j in days:
            fix[f"off_{shop}_{j}"] = 0
            for i in tiers[shop]:
                for k in shifts:
                    fix[f"y_{shop}_{j}_{i}_{k}"] = 0
    seen_crew, seen_day = set(), set()
    for row in rows:
        shop = shop_code(row["车间"])
        if shop not in shops:
            raise ValueError(f"这张按天排法只覆盖 {'、'.join(shops)}，没有 {shop}。")
        kind = str(row["类型"]).strip()
        if kind == "定员":
            if shop in seen_crew:
                raise ValueError(f"{shop} 的定员写了两次。")
            seen_crew.add(shop)
            i = _tier(d, shop, row["JPH"])
            kk = int(float(row["班次"]))
            if kk not in shifts:
                raise ValueError(f"没有 {kk} 班。")
            fix[f"crew_{shop}_{i}_{kk}"] = 1
        elif kind == "当日":
            day = int(float(row["日"]))
            j = day - 1
            if j not in days:
                raise ValueError(f"第 {day} 天超出这 {cfg['days']} 天。")
            if (shop, j) in seen_day:
                raise ValueError(f"{shop} 第 {day} 天写了两次。")
            seen_day.add((shop, j))
            jph, shift, state = _parse_state(row["状态"])
            if state == "停炉":
                fix[f"off_{shop}_{j}"] = 1
            elif state == "开工":
                i = _tier(d, shop, jph)
                if shift not in shifts:
                    raise ValueError(f"没有 {shift} 班。")
                fix[f"y_{shop}_{j}_{i}_{shift}"] = 1
            elif state != "保温":
                raise ValueError(f"状态看不懂：{row['状态']}。")
        else:
            raise ValueError(f"类型要写定员或当日，现在是 {kind}。")
    if any(s not in seen_crew for s in shops) or any((s, j) not in seen_day for s in shops for j in days):
        raise ValueError("排法没有覆盖每个车间的定员和每一天。")
    return fix


def _solver(cfg):
    tl = cfg.get("solver_time_limit", 120); gap = cfg.get("mip_rel_gap", 1e-3)
    solver, threads, seed = solve_meta.make_solver(tl, gap, cfg.get("threads"), cfg.get("solver_seed", 1))
    return solver, threads, seed, tl, gap

def solve(d, cfg, strategy="optimal", buf_max=None, duals=True):
    t0 = time.time(); P, v = build(d, cfg, strategy, buf_max)
    solver, threads, seed, tl, gap = _solver(cfg)
    P.solve(solver); mip_seconds = time.time() - t0; st = pulp.LpStatus[P.status]
    fixed = integer_assignment(P)
    meta = solve_meta.meta_from(P, pulp.value(P.objective), gap, tl, mip_seconds, threads, seed)
    cost = {k: pulp.value(e) or 0.0 for k, e in v["acc"].items()}; obj = pulp.value(P.objective)
    sched = []
    for j in v["D"]:
        row = dict(日=j + 1, 周末="是" if v["wk"][j] else "", 总装需求=round(v["need"][j]))
        for s in v["S"]:
            on = [(i, k) for i in v["I"][s] for k in v["K"] if v["y"][(s, j, i, k)].value() > 0.5]
            row[f"{s}_状态"] = (f"JPH{int(d['jph'][s][on[0][0]]['jph'])}×{on[0][1]}班" if on else ("停炉" if v["off"][(s, j)].value() > 0.5 else "保温/待机"))
            row[f"{s}_产量"] = round(v["q"][(s, j)].value()); row[f"{s}_启炉"] = round(v["st"][(s, j)].value())
        row["白车身缓存"] = round(v["B"][j].value()); row["PBS缓存"] = round(v["PB"][j].value()); row["缺货"] = round(v["sh"][j].value())
        sched.append(row)
    sp = None
    if duals:   # 影子价格：固定全部二进制（开停/班次/停炉）后解 LP，读白车身库容约束对偶值 = 库容 +1 台（全月）的节省
        P2, v2 = build(d, cfg, strategy, buf_max, fix=fixed); P2.solve(_solver(cfg)[0])
        try: sp = -sum(P2.constraints[f"bufmax_{j}"].pi or 0.0 for j in v["D"])
        except Exception: sp = None
    op = obj - cost.get("缺货惩罚", 0)
    kp = dict(策略=NAMES.get(strategy, strategy), 状态=st, 运营成本_万元=round(op / 1e4, 1), 单车_元=round(op / cfg["monthly_demand"]),
              能源_万元=round(sum(x for k, x in cost.items() if k.startswith(("能源", "启停", "需量"))) / 1e4, 1),
              人工_万元=round(sum(cost.get(k, 0) for k in ("人工", "休息日加班费", "班车外包", "借调节省人工", "借调占用(借出方停工日不能省)")) / 1e4, 1),
              借调_人=round(sum(cost.get(k, 0) for k in ("借调节省人工",)) / -(d["g"]["wage_per_head_month"] * d["g"].get("burden_rate", 1.0)), 1),
              换档_万元=round(cost.get("JPH换档", 0) / 1e4, 1),
              库存_万元=round(cost.get("缓存持有", 0) / 1e4, 1),
              焊装开工天=sum(1 for r in sched if "JPH" in r["BIW_状态"]), 涂装开工天=sum(1 for r in sched if "JPH" in r["PNT_状态"]),
              焊装定员班次=next((f"JPH{int(d['jph']['BIW'][i]['jph'])}×{kk}班定员" for (s_, i, kk), var in v["crew"].items() if s_ == "BIW" and (var.value() or 0) > 0.5), "-"),
              涂装定员班次=next((f"JPH{int(d['jph']['PNT'][i]['jph'])}×{kk}班定员" for (s_, i, kk), var in v["crew"].items() if s_ == "PNT" and (var.value() or 0) > 0.5), "-"),
              涂装启炉次数=sum(r["PNT_启炉"] for r in sched), 最高白车身缓存=max(r["白车身缓存"] for r in sched),
              平均白车身缓存=round(sum(r["白车身缓存"] for r in sched) / len(sched)), 缺货台=sum(r["缺货"] for r in sched),
              需量kW=round(v["peak"].value()), 库容影子价格_元每台月=None if sp is None else round(sp, 1), 求解秒=round(time.time() - t0, 1),
              Gap=None if meta.get("Gap") is None else round(meta["Gap"], 6),
              下界_万元=None if meta.get("下界") is None else round(meta["下界"] / 1e4, 1),
              触时限="是" if meta.get("触时限") else "", 种子=meta.get("种子"), 线程=meta.get("线程"))
    if v["pmd"]: kp["PM停线天"] = sum(1 for j in v["pmd"] if not v["wk"][j])   # A08 开启时才加这一列
    return dict(kpi=kp, cost=cost, sched=sched, obj=obj, fix=fixed)

def _key(d, cfg, strategy, buf_max):
    import engine as en
    src = b"".join(open(os.path.join(H, n), "rb").read() for n in ("daily.py", "energy.py", "cost_functions.py"))
    return hashlib.sha1((en._canon({k: v for k, v in d.items() if k != "plant"}) + en._canon(cfg) + strategy + repr(buf_max)).encode() + src).hexdigest()[:20]

def solve_cached(d, cfg, strategy, buf_max=None, duals=True, use_cache=True):
    p = os.path.join(CACHE, "daily_" + _key(d, cfg, strategy, buf_max) + f"_{int(duals)}.pkl")
    if use_cache and os.path.exists(p): r = pickle.load(open(p, "rb")); r["cached"] = True; return r
    r = solve(d, cfg, strategy, buf_max, duals); r["cached"] = False
    os.makedirs(CACHE, exist_ok=True); pickle.dump(r, open(p, "wb")); return r

def shadow_fd(d, cfg, strategy="optimal", step=100, use_cache=True):
    """有限差分影子价格：库容 ±step 台重解 MIP（排程可随之改变），元/台·月"""
    b0 = cfg["biw_buffer_max"]; r0 = solve_cached(d, cfg, strategy, None, False, use_cache)
    rows = [dict(策略=NAMES[strategy], 库容_台=b0, 运营成本_万元=r0["kpi"]["运营成本_万元"], 涂装开工天=r0["kpi"]["涂装开工天"], 涂装启炉次数=r0["kpi"]["涂装启炉次数"], 每台库容月节省_元="基准")]
    for db in (-2 * step, -step, step, 2 * step):
        r = solve_cached(d, cfg, strategy, b0 + db, False, use_cache)
        rows.append(dict(策略=NAMES[strategy], 库容_台=b0 + db, 运营成本_万元=r["kpi"]["运营成本_万元"], 涂装开工天=r["kpi"]["涂装开工天"],
                         涂装启炉次数=r["kpi"]["涂装启炉次数"], 每台库容月节省_元=round((r0["obj"] - r["obj"]) / db)))
    return sorted(rows, key=lambda r: r["库容_台"])

def demand_sweep(d, cfg, levels=None, strategies=("sync", "optimal"), use_cache=True):
    """需求敏感性：低需求时模型是否"开几天停几天"、库容是否成为瓶颈（看影子价格）"""
    rows = []
    for q in levels or cfg.get("demand_sweep", [6000, 8000, 10000]):
        c = dict(cfg, monthly_demand=q)
        for s in strategies:
            k = solve_cached(d, c, s, None, True, use_cache)["kpi"]
            rows.append(dict(月需求=q, **{kk: k[kk] for kk in ("策略", "运营成本_万元", "单车_元", "能源_万元", "人工_万元", "库存_万元", "焊装定员班次", "涂装定员班次",
                                                           "焊装开工天", "涂装开工天", "涂装启炉次数", "最高白车身缓存", "库容影子价格_元每台月")}))
    return rows

def with_dispatch(d, share):
    e = copy.deepcopy(d)
    for s in e.get("lflex", {}): e["lflex"][s]["dispatch_share"] = share
    return e

def dispatch_sweep(d, cfg, shares=None, levels=None, use_cache=True):
    """v5.2：派遣比 × 月需求。'开几天停几天'值不值 = 连续生产成本 − 模型最优成本；库容是否卡住 = 影子价格 > 0"""
    rows = []
    for sh_ in shares or cfg.get("dispatch_sweep", [0.0, 0.2, 0.5]):
        e = with_dispatch(d, sh_)
        for q in levels or cfg.get("demand_sweep", [6000, 8000, 10000]):
            c = dict(cfg, monthly_demand=q)
            ro = solve_cached(e, c, "optimal", None, True, use_cache)["kpi"]; rc = solve_cached(e, c, "weekdays", None, False, use_cache)["kpi"]
            rows.append(dict(派遣比=f"{int(sh_*100)}%", 停工日可省人工比=f"{cf.flex_var_share(e, 'BIW')*100:.0f}%", 月需求=q,
                             最优_万元=ro["运营成本_万元"], 每工作日都开_万元=rc["运营成本_万元"], 开停策略节省_万元=round(rc["运营成本_万元"] - ro["运营成本_万元"], 1),
                             焊装开工天=ro["焊装开工天"], 涂装开工天=ro["涂装开工天"], 涂装启炉次数=ro["涂装启炉次数"], 焊装定员班次=ro["焊装定员班次"], 涂装定员班次=ro["涂装定员班次"],
                             最高白车身缓存=ro["最高白车身缓存"], 借调_人=ro["借调_人"], 库容影子价格_元每台月=ro["库容影子价格_元每台月"], 人工_万元=ro["人工_万元"], 能源_万元=ro["能源_万元"]))
    return rows

def wcsv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, keys, restval=""); w.writeheader(); w.writerows(rows)

def main(strategies=("continuous", "sync", "optimal", "two_shift"), use_cache=True, base=None, d=None, cfg=None):
    os.makedirs(OUT, exist_ok=True); d = d or dl.load(base); cfg = cfg or load_cfg(base); res = {}
    for s in strategies:
        res[s] = solve_cached(d, cfg, s, None, True, use_cache)
        wcsv(os.path.join(OUT, f"daily_schedule_{s}.csv"), res[s]["sched"]); print(res[s]["kpi"])
    wcsv(os.path.join(OUT, "daily_strategy_summary.csv"), [res[s]["kpi"] for s in strategies])
    keys = list(dict.fromkeys(k for s in strategies for k in res[s]["cost"]))
    wcsv(os.path.join(OUT, "daily_cost_breakdown.csv"), [dict(科目=k, **{NAMES[s]: round(res[s]["cost"].get(k, 0)) for s in strategies}) for k in keys])
    fd = shadow_fd(d, cfg, "optimal", use_cache=use_cache); wcsv(os.path.join(OUT, "daily_buffer_shadow.csv"), fd)
    for r in fd: print(r)
    sw = demand_sweep(d, cfg, use_cache=use_cache)
    wcsv(os.path.join(OUT, "daily_demand_sweep.csv"), sw)
    for r in sw: print(r)
    ds = dispatch_sweep(d, cfg, use_cache=use_cache); wcsv(os.path.join(OUT, "daily_dispatch_sweep.csv"), ds)
    for r in ds: print(r)
    return res, fd

if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x.startswith("--strategies=")]
    main(tuple(a[0].split("=")[1].split(",")) if a else ("continuous", "sync", "optimal", "two_shift"), "--no-cache" not in sys.argv)
