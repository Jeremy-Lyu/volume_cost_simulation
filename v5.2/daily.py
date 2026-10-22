"""v5.1 按天排产层：焊装 → 白车身缓存 → 涂装 → PBS（涂装后缓存）→ 总装（示例数据）
决策（每车间每天）：开/不开（二进制）、开几班、月度 JPH 档与班组数；不开时 保温 还是 停炉（off）；停炉后再开计一次启炉成本
约束：白车身缓存日平衡 B[d]=B[d-1]+焊装产出−涂装投入，下限 ≤ B ≤ 库容；PBS 同理供总装（总装按工作日均衡拉动）；月末缓存不低于月初
成本：人工（班组月薪 + 夜班补贴 + 休息日加班费）+ 班车外包 + 分时能源（运行电/待机电/天然气/启停/需量）+ 缓存持有与资金占用 + 缺货惩罚
策略：continuous=工作日三班连续、周末保温；sync=焊装与涂装同开同停（模型选哪天开）；optimal=模型自由排；two_shift=工作日两班+周末停炉（参考）
参数：data/daily_config.json + 能源参数（energy_config.json / shop_energy.csv / tou_*.csv），全部 ⚠ 暂定
用法：python3 daily.py [--strategies=continuous,sync,optimal,two_shift] [--no-cache]"""
import copy, csv, json, os, sys, time, hashlib, pickle
import pulp
import data_loader as dl, cost_functions as cf, energy as E
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
    return dict(el_run=run, el_sb=sb, gas=gas), o["jph"] * effh * cfg["run_rate"]

def build(d, cfg, strategy="optimal", buf_max=None, fix=None):
    t = cfg["month"]; D = range(cfg["days"]); S = cfg["shops"]; K = [k for k in sorted(d["shift"]) if k > 0]
    wk = [(cfg["first_weekday"] + i) % 7 >= 5 for i in D]; nwd = sum(1 for w in wk if not w)
    need = [0 if wk[i] else cfg["monthly_demand"] / nwd for i in D]
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
                    lost_switch.append((s, crew[(s, i, kk)] * js["lost_days"] * o["jph"] * d["shift"][kk]["eff_hours_per_shift"] * kk * cfg["run_rate"]))
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
                else: P += pulp.lpSum(y[(s, j, i, 3)] for i in I[s]) == 1, f"c3_{s}_{j}"
    elif strategy == "two_shift":
        for s in S:
            for j in D:
                if wk[j]: P += opn[(s, j)] == 0, f"tw_{s}_{j}"; P += off[(s, j)] == 1, f"to_{s}_{j}"
                else: P += pulp.lpSum(y[(s, j, i, 2)] for i in I[s]) == 1, f"t2_{s}_{j}"
    elif strategy == "weekdays":   # v5.2 对照：每个工作日都开（班次可选），不主动停线
        for s in S:
            for j in D:
                if not wk[j]: P += opn[(s, j)] == 1, f"wd_{s}_{j}"
    elif strategy == "sync":
        for j in D:
            for k in K: P += pulp.lpSum(y[(a, j, i, k)] for i in I[a]) == pulp.lpSum(y[(b, j, i, k)] for i in I[b]), f"sync_{j}_{k}"
    if cfg.get("same_shift_as_crew"):   # v5.2 敏感性：开工日必须开满班组的班数（不能"每天少开一班"），只能整天停
        for s in S:
            for j in D:
                for i in I[s]:
                    for k in K: P += y[(s, j, i, k)] <= crew[(s, i, k)], f"ssc_{s}_{j}_{i}_{k}"
    for s, kk0 in (cfg.get("fix_crew") or {}).items():   # v5.2：班组规模按月已定（例如沿用上月 2 班定员），当月只能靠开停天数调节
        P += pulp.lpSum(crew[(s, i, kk)] for i in I[s] for kk in K if kk == kk0) == 1, f"fixcrew_{s}"
    if fix:
        for v in P.variables():
            if v.name in fix: v.lowBound = v.upBound = fix[v.name]; v.cat = "Continuous"
    accs = {k_: pulp.lpSum(v_) for k_, v_ in acc.items()}
    P += pulp.lpSum(accs.values())
    return P, dict(acc=accs, y=y, off=off, st=st, q=q, B=B, PB=PB, sh=sh, peak=peak, crew=crew, wk=wk, need=need, caps=caps, D=D, S=S, K=K, I=I)

def _solver(cfg):
    tl = cfg.get("solver_time_limit", 120); gap = cfg.get("mip_rel_gap", 1e-3)
    return pulp.HiGHS(msg=False, timeLimit=tl, gapRel=gap) if "HiGHS" in pulp.listSolvers(True) else pulp.PULP_CBC_CMD(msg=False, timeLimit=int(tl), gapRel=gap)

def solve(d, cfg, strategy="optimal", buf_max=None, duals=True):
    t0 = time.time(); P, v = build(d, cfg, strategy, buf_max); P.solve(_solver(cfg)); st = pulp.LpStatus[P.status]
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
        fix = {var.name: round(var.value()) for var in P.variables() if var.cat == "Integer"}
        P2, v2 = build(d, cfg, strategy, buf_max, fix=fix); P2.solve(_solver(cfg))
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
              焊装班组=next((f"JPH{int(d['jph']['BIW'][i]['jph'])}×{kk}班组" for (s_, i, kk), var in v["crew"].items() if s_ == "BIW" and (var.value() or 0) > 0.5), "-"),
              涂装班组=next((f"JPH{int(d['jph']['PNT'][i]['jph'])}×{kk}班组" for (s_, i, kk), var in v["crew"].items() if s_ == "PNT" and (var.value() or 0) > 0.5), "-"),
              涂装启炉次数=sum(r["PNT_启炉"] for r in sched), 最高白车身缓存=max(r["白车身缓存"] for r in sched),
              平均白车身缓存=round(sum(r["白车身缓存"] for r in sched) / len(sched)), 缺货台=sum(r["缺货"] for r in sched),
              需量kW=round(v["peak"].value()), 库容影子价格_元每台月=None if sp is None else round(sp, 1), 求解秒=round(time.time() - t0, 1))
    return dict(kpi=kp, cost=cost, sched=sched, obj=obj)

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
            rows.append(dict(月需求=q, **{kk: k[kk] for kk in ("策略", "运营成本_万元", "单车_元", "能源_万元", "人工_万元", "库存_万元", "焊装班组", "涂装班组",
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
                             焊装开工天=ro["焊装开工天"], 涂装开工天=ro["涂装开工天"], 涂装启炉次数=ro["涂装启炉次数"], 焊装班组=ro["焊装班组"], 涂装班组=ro["涂装班组"],
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
