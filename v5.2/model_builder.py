"""月度模型。每个车间、每个月只选一个档 y：JPH × 班次（0/1/2/3）。

build(d) 按这个顺序往同一个问题上加式子，缺表的段落整段跳过，基础口径不变：
  1. 每个候选档的人工、能源、制造费用，加进目标
  2. 停工日、借调、换档（有 labor_flex / jph_switch 才建）
  3. 缓存、成品、物流、固定制造费用；物料不进目标
  4. 约束：每月一档、产能、订单平衡、车间之间的缓存平衡
  5. 可选：人数变化上限、JPH 相邻月只变一档、班次按季固定、权重、锁定已选方案

solve(P, d) 调用 HiGHS，没有就用 CBC。日常命令不直接调这两个函数，走 engine.solved。
目标是成本最低。配了 margin.csv 之后，目标改为成本减去边际贡献。"""
import pulp
import cost_functions as cf
def build(d, jph_step=False, shift_quarter=False, util_cap=None, head_change=None, fix_y=None,
          head_up=None, head_dn=None, weights=None, cuts=None, cut_min_diff=2):
    """可选约束（默认关闭）：util_cap=正常班产能利用率上限(如0.9，加班产能另计)；head_change=各车间人数月环比变化上限(如0.05)；
    head_up/head_dn=人数上行/下行非对称上限(如 0.05/0.10，模拟招聘提前期与裁员受限)；
    fix_y=固定方案{(s,i,k,t):0/1}（蒙特卡洛评估用）；jph_step=相邻月 JPH 最多变一档；shift_quarter=班次数每季度固定（每季度最多在季初调整一次）"""
    S, M, T = d["shops"], d["models"], d["months"]
    c = d.setdefault("coarse", {})
    if head_up is None and c.get("head_up") not in (None, ""):
        head_up = float(c["head_up"])
    if head_dn is None and c.get("head_dn") not in (None, ""):
        head_dn = float(c["head_dn"])
    post_eff = float(c.get("post_switch_eff") or 1)
    moq_fee = float(c.get("moq_fee") or 0)
    restart_cost = float(c.get("restart_cost") or 0)
    if not d.get("_coarse_pm"):
        pm = float(c.get("pm_days") or 0)
        d["_coarse_pm"] = True
        if pm > 0 and d.get("days"):
            trough = min(T, key=lambda t: (d["days"][t], t))
            d["down"] = dict(d.get("down") or {})
            for s in S:
                d["down"][(s, trough)] = d["down"].get((s, trough), 0) + pm
    P = pulp.LpProblem("JPH_cost", pulp.LpMinimize)
    V = (lambda n, idx, **kw: P.add_variable_dicts(n, idx, **kw)) if hasattr(P, "add_variable_dicts") else pulp.LpVariable.dicts
    ni = {s: len(d["jph"][s]) for s in S}
    K = sorted(d["shift"])
    # v4 规则3：0 班只挂在最低档(i=0)，避免等价重复解
    C = [(s, i, k, t) for s in S for i in range(ni[s]) for k in K for t in T if k > 0 or i == 0]
    y = V("y", C, cat="Binary")
    Y = lambda s, i, k, t: y.get((s, i, k, t), 0)
    ot = V("ot", [(s,i,t) for s in S for i in range(ni[s]) for t in T], lowBound=0)    # 36h/人 以内的线体加班小时
    otx = V("otx", [(s,i,t) for s in S for i in range(ni[s]) for t in T], lowBound=0)  # v4 规则4：超限部分
    x = V("x", [(s,m,t) for s in S for m in M for t in T], lowBound=0)
    short = V("short", [(m,t) for m in M for t in T], lowBound=0)    # v4：流失（只在期末非零）
    bl = V("bl", [(m,t) for m in M for t in T], lowBound=0)          # v4 规则2：月末积压（延期到下月）
    inv = V("inv", [(s,m,t) for s in S[:-1] for m in M for t in T], lowBound=0)
    o = lambda s, i: d["jph"][s][i]
    fh = d["g"].get("fg_hold_cost_per_unit_month", 0.0)
    cap_rate = d["g"].get("capital_rate_month", 0.0)
    use_fg = bool(d.get("ship")) or fh > 0
    ship = V("ship", [(m,t) for m in M for t in T], lowBound=0) if use_fg else None
    fginv = V("fginv", [(m,t) for m in M for t in T], lowBound=0) if use_fg else None
    deliver = (lambda m, t: ship[(m,t)]) if use_fg else (lambda m, t: x[(S[-1],m,t)])
    cdec = {s: cf.chg_mode(d, s) == "decision" for s in S}
    ccol = {s: cf.chg_mode(d, s) == "color" for s in S}
    on = V("on", [(s,m,t) for s in S for m in M for t in T], cat="Binary") if any(cdec.values()) else None
    colors = sorted({d.get("color", {}).get(m) for m in M if d.get("color", {}).get(m)})
    onc = V("onc", [(s,c,t) for s in S if ccol[s] for c in colors for t in T], cat="Binary") if any(ccol.values()) and colors else None
    use_line = bool(d.get("line_supply"))
    calloff = V("calloff", [(m,t) for m in M for t in T], lowBound=0) if use_line else None
    line_inv = V("lineinv", [(m,t) for m in M for t in T], lowBound=0) if use_line else None
    st = {s: {(i,t): pulp.LpVariable(f"st_{s}_{i}_{t}", lowBound=0, cat="Integer") for i in range(ni[s]) for t in T}
          for s in S if cdec[s] or ccol[s]}
    # ===== v4：目标函数按科目构造，报表直接取值（acc[科目] = 线性表达式），分项之和 ≡ 目标 =====
    acc = {}
    def add(k, e): acc.setdefault(k, []).append(e)
    for (s,i,k,t) in C:
        for kk, vv in cf.fixed_breakdown(d,s,o(s,i),k,t).items():
            if vv: add(kk, vv * y[(s,i,k,t)])
    for (s,i,t) in ot:
        add("加班", cf.ot_labor_per_hour(d,s,o(s,i)) * (ot[(s,i,t)] + otx[(s,i,t)]))
        add("超限加班溢价", cf.ot_excess_per_hour(d,s,o(s,i)) * otx[(s,i,t)])
        add("能源变动", cf.ot_energy_per_hour(d,s,o(s,i),t) * (ot[(s,i,t)] + otx[(s,i,t)]))   # v5.1：加班按其时段电价 + 运行气
    for (s,m,t) in x:
        for kk, c in cf.var_parts(d, s, t).items():
            if c: add(kk, c * x[(s,m,t)])
    ev = None
    if cf.en_.active(d):   # v5.1：单车电耗 × 所选班次加权电价。按班次拆分产量 w[s,k,t]（凸包式，比大 M 紧，求解快）：
        # Σ_k w = Σ_m x；w[s,k,t] ≤ 该班次最大产能(含加班) × Σ_i y[s,i,k,t]；能源变动 = Σ_k 单车kWh × 班次电价_k × w
        Kp = [k for k in K if k]
        ev = V("evw", [(s,k,t) for s in S for k in Kp for t in T], lowBound=0)
        hc = d["g"]["ot_hard_cap_per_head_month"]
        for s in S:
            for t in T:
                P += pulp.lpSum(ev[(s,k,t)] for k in Kp) == pulp.lpSum(x[(s,m,t)] for m in M), f"evsum_{s}_{t}"
                for k in Kp:
                    capk = max(cf.capacity(d,s,o(s,i),k,t) + cf.ot_units(d,s,o(s,i),t,hc*k) for i in range(ni[s]))
                    P += ev[(s,k,t)] <= capk * pulp.lpSum(Y(s,i,k,t) for i in range(ni[s])), f"evcap_{s}_{k}_{t}"
                    add("能源变动", d["shop"][s]["kwh_per_unit"] * cf.price(d,t,k) * ev[(s,k,t)])
    # ===== v5.2：停工日（人工弹性）、跨车间借调、JPH 换档 =====
    sdo, bw, swv, lost, learn = {}, {}, {}, {}, {}
    use_flex = bool(d.get("lflex")); use_sw = bool(d.get("jsw"))
    for s in S:
        for t in T:
            if use_flex and cf.lflex(d, s):
                for i in range(ni[s]):
                    for k in K:
                        if not k: continue
                        v_ = pulp.LpVariable(f"sd_{s}_{i}_{k}_{t}", lowBound=0); sdo[(s,i,k,t)] = v_
                        P += v_ <= max(cf.workdays(d,s,t) - 1, 0) * Y(s,i,k,t), f"sdl_{s}_{i}_{k}_{t}"
                        sv = cf.stop_day_saving(d, s, o(s,i), k, t)
                        add("停工日人工节省", -sv["人工"] * v_); add("停工日能源节省", -sv["能源"] * v_)
                bw[(s,t)] = pulp.LpVariable(f"bw_{s}_{t}", lowBound=0)
                P += bw[(s,t)] <= cf.lflex(d,s)["borrow_limit"] * pulp.lpSum((o(s,i)["heads"]+cf.indirect_heads(d,s,o(s,i)))*k*Y(s,i,k,t) for i in range(ni[s]) for k in K), f"bwl_{s}_{t}"
                g_ = d["g"]; wb = g_["wage_per_head_month"] * g_.get("burden_rate", 1.0)
                add("借调节省人工", -wb * bw[(s,t)])   # 借入车间少雇 bw 人
                add("借调占用(借出方停工日不能省)", wb / cf.paid_days(d,s) * cf.flex_var_share(d,s) * cf.workdays(d,s,t) * bw[(s,t)])
            if use_sw and cf.jph_switch(d, s) and t != T[0]:
                js = cf.jph_switch(d, s)
                lost[(s,t)] = pulp.LpVariable(f"jlost_{s}_{t}", lowBound=0)
                for i in range(ni[s]):
                    zi = pulp.lpSum(Y(s,i,k,t) for k in K if k); zp = pulp.lpSum(Y(s,i,k,t-1) for k in K if k)
                    swv[(s,i,t)] = pulp.LpVariable(f"jsw_{s}_{i}_{t}", lowBound=0)
                    P += swv[(s,i,t)] >= zi - zp, f"jswc_{s}_{i}_{t}"
                    add("JPH换档", js["cost_per_switch"] * swv[(s,i,t)])
                    for k in K:
                        if k: P += lost[(s,t)] >= js["lost_days"] * cf.cap_per_day(d,s,o(s,i),k,t) * (Y(s,i,k,t) - zp), f"jlo_{s}_{i}_{k}_{t}"
                        if k and post_eff < 1 - 1e-9:
                            if (s, t) not in learn:
                                learn[(s, t)] = pulp.LpVariable(f"jlearn_{s}_{t}", lowBound=0)
                            P += learn[(s, t)] >= (1 - post_eff) * cf.capacity(d, s, o(s, i), k, t) * (Y(s, i, k, t) - zp), f"jle_{s}_{i}_{k}_{t}"
    if use_flex:   # 借调人力来源：借出车间停工日的空闲人·天 ≥ 借入人·天
        for t in T:
            P += pulp.lpSum(bw[(s,t)] * cf.workdays(d,s,t) for s in S if (s,t) in bw) <= \
                 pulp.lpSum((o(s,i)["heads"]+cf.indirect_heads(d,s,o(s,i)))*k*sdo[(s,i,k,t)] for (s,i,k,tt) in sdo if tt == t), f"bwsrc_{t}"
    if restart_cost > 0 and sdo:   # 有停工日的车间月计一次复产质量。0 = 不建这个变量
        for s in S:
            for t in T:
                tot = pulp.lpSum(sdo[(s, i, k, t)] for i in range(ni[s]) for k in K if (s, i, k, t) in sdo)
                flag = pulp.LpVariable(f"rst_{s}_{t}", cat="Binary")
                P += tot <= max(cf.workdays(d, s, t), 1) * flag, f"rstc_{s}_{t}"
                add("复产质量", restart_cost * flag)
    if moq_fee > 0 and len(T) > 1:   # 首车间产量月环比超过 10% 的月份，收一笔加急费
        big = sum(d["demand"].values()) + 1
        for t in T[1:]:
            prev = pulp.lpSum(x[(S[0], m, t - 1)] for m in M)
            cur = pulp.lpSum(x[(S[0], m, t)] for m in M)
            pos = pulp.LpVariable(f"moq_pos_{t}", lowBound=0)
            neg = pulp.LpVariable(f"moq_neg_{t}", lowBound=0)
            P += pos - neg == cur - prev, f"moq_bal_{t}"
            exc = pulp.LpVariable(f"moq_exc_{t}", lowBound=0)
            P += exc >= pos + neg - 0.10 * prev, f"moq_ex_{t}"
            trig = pulp.LpVariable(f"moq_b_{t}", cat="Binary")
            P += exc <= big * trig, f"moq_on_{t}"
            add("起订加急", moq_fee * trig)
    def lostcap(s, t):
        return pulp.lpSum(cf.cap_per_day(d,s,o(s,i),k,t) * sdo[(s,i,k,t)] for i in range(ni[s]) for k in K if (s,i,k,t) in sdo) + lost.get((s,t), 0) + learn.get((s,t), 0)
    for (s,m,t) in inv:
        add("缓存持有", d["shop"][s]["hold_cost_per_unit_month"] * inv[(s,m,t)])
        if cap_rate: add("库存资金", cap_rate * cf.unit_value(d,m,t) * inv[(s,m,t)])
    if use_fg:
        for (m,t) in fginv:
            if fh: add("成品持有", fh * fginv[(m,t)])
            if cap_rate: add("库存资金", cap_rate * cf.unit_value(d,m,t) * fginv[(m,t)])
    if d.get("margin"):
        for m in M:
            for t in T:
                v_ = cf.margin(d, m, t)
                if v_: add("−边际贡献", -v_ * deliver(m,t))
    for s in S:
        if cdec[s] or ccol[s]:
            for (i,t) in st[s]: add("换型", d["chg"][s]["cost_per_setup"] * st[s][(i,t)])
    if use_line and cap_rate:
        for m in M:
            for t in T:
                if cf.line_row(d, m, t): add("线前库存", cap_rate * cf.mat_cost(d, m, t) * line_inv[(m,t)])
    add("缺口惩罚(流失)", d["g"]["shortage_penalty"] * pulp.lpSum(short.values()))
    add("延期成本", d["g"]["backlog_cost_per_unit_month"] * pulp.lpSum(bl[(m,t)] for m in M for t in T[:-1]))
    co2over = None
    if cf.use_carbon_quota(d):
        co2over = V("co2over", [(t,) for t in T], lowBound=0)
        for t in T: add("碳配额购买", cf.carbon_price(d) * co2over[(t,)])
    def add_lanes(ls, cover, tag, name):
        nonlocal P
        if not ls: return None
        lim = int(sum(d["demand"].values()) / min(l["capacity"] for l in ls)) + 1
        tr = V(f"trips_{tag}", [(l["lane"], t) for l in ls for t in T], cat="Integer", lowBound=0)
        for t in T:
            P += pulp.lpSum(tr[(l["lane"],t)]*l["capacity"] for l in ls) >= cover(t), f"tripcov_{tag}_{t}"
        for l in ls:
            for t in T:
                add(name, l["cost_per_trip"] * tr[(l["lane"],t)])
                if l.get("fixed_month_cost"):
                    u = pulp.LpVariable(f"u_{tag}_{l['lane'].replace('-','_')}_{t}", cat="Binary")
                    P += tr[(l["lane"],t)] <= lim * u; P += tr[(l["lane"],t)] >= u
                    add(name, l["fixed_month_cost"] * u)
        return tr
    lanes = d.get("lanes", [])
    def inbound_cover(t):
        if not use_line: return pulp.lpSum(x[(S[0],m,t)] for m in M)
        terms = []
        for m in M:
            row = cf.line_row(d, m, t)
            terms.append(calloff[(m,t)] + row["git_incoming"] if row else x[(S[0],m,t)])
        return pulp.lpSum(terms)
    trips = add_lanes([l for l in lanes if l["scope"] != "inbound"], lambda t: pulp.lpSum(deliver(m,t) for m in M), "out", "物流-成品")
    trips_in = add_lanes([l for l in lanes if l["scope"] == "inbound"], inbound_cover, "in", "物流-入厂")
    add("OH", sum(d["shop"][s]["oh_fixed_month"] for s in S) * len(T))   # 固定 OH（常数）
    if cf.tooling_monthly(d): add("模具摊销", cf.tooling_monthly(d))
    if cf.dep_monthly(d): add("设备折旧", cf.dep_monthly(d) * len(T))
    acc = {k: pulp.lpSum(v) for k, v in acc.items()}
    P += pulp.lpSum(acc.values())
    def add(k, e): acc[k] = acc.get(k, 0) + e      # v5：之后追加的科目（权重项）
    if co2over is not None:
        for t in T:
            P += cf.co2_per_unit(d) * pulp.lpSum(x[(S[-1],m,t)] for m in M) <= cf.carbon_quota(d) + co2over[(t,)], f"co2_{t}"
    for s in S:
        for t in T:
            n = range(ni[s])
            P += pulp.lpSum(Y(s,i,k,t) for i in n for k in K) == 1, f"one_{s}_{t}"
            for i in n:   # v4 规则4：每个定员班次的人员都可加班 → 线体加班小时上限 = 人均上限 × 班次数；36h 内为常规，超出为超限（有溢价、有绝对上限）
                kk = pulp.lpSum(k * Y(s,i,k,t) for k in K)
                P += ot[(s,i,t)] <= d["shop"][s]["ot_max_hours_month"] * kk, f"otl_{s}_{i}_{t}"
                P += otx[(s,i,t)] <= (d["g"]["ot_hard_cap_per_head_month"] - d["shop"][s]["ot_max_hours_month"]) * kk, f"otx_{s}_{i}_{t}"
            if cdec[s] or (ccol[s] and onc is not None):   # 产能扣除换型工时。decision：每个额外车型至少一次；color：每种在产颜色至少一次
                P += pulp.lpSum(x[(s,m,t)] for m in M) <= pulp.lpSum(cf.capacity(d,s,o(s,i),k,t)*Y(s,i,k,t) for i in n for k in K) \
                     - pulp.lpSum(o(s,i)["jph"]*o(s,i).get("mix_eff", 1.0)*d["chg"][s]["hours_per_setup"]*st[s][(i,t)] for i in n) \
                     + pulp.lpSum(cf.ot_units(d,s,o(s,i),t,ot[(s,i,t)]+otx[(s,i,t)]) for i in n) - lostcap(s,t), f"cap_{s}_{t}"
                for i in n: P += st[s][(i,t)] <= (len(colors) or len(M)) * pulp.lpSum(Y(s,i,k,t) for k in K), f"stlink_{s}_{i}_{t}"
                if cdec[s]:
                    P += pulp.lpSum(st[s][(i,t)] for i in n) >= pulp.lpSum(on[(s,m,t)] for m in M) - 1, f"stlb_{s}_{t}"
                    for m in M:
                        P += x[(s,m,t)] <= d["cap"][(s,m,t)] * on[(s,m,t)], f"onM_{s}_{m}_{t}"
                        P += x[(s,m,t)] >= on[(s,m,t)], f"onm_{s}_{m}_{t}"
                else:
                    P += pulp.lpSum(st[s][(i,t)] for i in n) >= pulp.lpSum(onc[(s,c,t)] for c in colors) - 1, f"stcol_{s}_{t}"
                    for c in colors:
                        ms = [m for m in M if d["color"].get(m) == c]
                        volc = pulp.lpSum(x[(s,m,t)] for m in ms)
                        big = sum(d["cap"][(s,m,t)] for m in ms) or 1
                        P += volc <= big * onc[(s,c,t)], f"oncM_{s}_{c}_{t}"
                        batch = d.get("color_batch", {}).get(c, 0)
                        if batch: P += volc >= batch * onc[(s,c,t)], f"batch_{s}_{c}_{t}"
                    for m in M: P += x[(s,m,t)] <= d["cap"][(s,m,t)], f"lim_{s}_{m}_{t}"
            else:
                P += pulp.lpSum(x[(s,m,t)] for m in M) <= pulp.lpSum(cf.capacity(d,s,o(s,i),k,t)*Y(s,i,k,t) for i in n for k in K) \
                     + pulp.lpSum(cf.ot_units(d,s,o(s,i),t,ot[(s,i,t)]+otx[(s,i,t)]) for i in n) - lostcap(s,t), f"cap_{s}_{t}"
                for m in M: P += x[(s,m,t)] <= d["cap"][(s,m,t)], f"lim_{s}_{m}_{t}"
            rw = cf.rwk(d, s)   # 返修区并联约束：返修工时需求 ≤ 返修区可用工时（与产线同班次）
            if rw:
                P += (1.0-cf.ftt(d,s))*rw["hours_per_unit"]*pulp.lpSum(x[(s,m,t)] for m in M) \
                     <= rw["stations"]*pulp.lpSum(cf.hours(d,k,t,s)*Y(s,i,k,t) for i in n for k in K), f"rwk_{s}_{t}"
    for m in M:
        for t in T:   # v4 规则2：积压平衡 上月积压 + 本月需求 = 本月交付 + 本月积压；期末积压 = 流失
            pb = bl[(m,t-1)] if t > T[0] else 0
            P += pb + d["demand"][(t,m)] == deliver(m,t) + bl[(m,t)], f"bl_{m}_{t}"
            if t == T[-1]: P += short[(m,t)] == bl[(m,t)], f"lost_{m}_{t}"
            else: P += short[(m,t)] == 0, f"nolost_{m}_{t}"
            if use_fg:   # 成品库平衡：上月成品 + 本月产量 = 本月发货 + 本月成品
                prev = fginv[(m,t-1)] if t > T[0] else 0
                P += prev + x[(S[-1],m,t)] == ship[(m,t)] + fginv[(m,t)], f"fg_{m}_{t}"
                sc = cf.ship_cap(d, m, t)     # 发运能力上限（船期/承运商/车位）
                if sc is not None: P += ship[(m,t)] <= sc, f"shipcap_{m}_{t}"
            else:
                sc = cf.ship_cap(d, m, t)
                if sc is not None: P += x[(S[-1],m,t)] <= sc, f"ship_{m}_{t}"
            if (m, t) in d.get("supply", {}): P += x[(S[-1],m,t)] <= d["supply"][(m,t)], f"sup_{m}_{t}"  # 零件供应上限(场景旋钮)；S[-1]=车间链最后一个(总装)
            oc = cf.order_cap(d, m, t)
            if oc is not None:   # 当月可分配订单：产量和发货都不能超过交集上限。产量为 0 表示前期成品已够付这批订单
                P += x[(S[-1],m,t)] <= oc, f"ord_{m}_{t}"
                if use_fg: P += ship[(m,t)] <= oc, f"ordship_{m}_{t}"
            sl = cf.slot_cap(d, m, t)
            if sl is not None: P += x[(S[-1],m,t)] <= sl, f"slot_{m}_{t}"  # 周计划回写的槽位上限
            row = cf.line_row(d, m, t) if use_line else None
            if row:   # 线前库存：期初/上月 + 在途 + 叫料 = 期末 + 首车间消耗×(1+报废净率)
                prev = line_inv[(m,t-1)] if t > T[0] else row["opening_stock"]
                net = 1.0 + row["scrap_rate"] * (1.0 - row["cancel_rate"])
                P += prev + row["git_incoming"] + calloff[(m,t)] == line_inv[(m,t)] + net * x[(S[0],m,t)], f"line_{m}_{t}"
                P += line_inv[(m,t)] >= row["safety_buffer"], f"safe_{m}_{t}"
                P += calloff[(m,t)] <= row["calloff_cap"], f"coff_{m}_{t}"
            for a, b in zip(S[:-1], S[1:]):     # 流平衡：上游产出 + 上月缓存 = 下游消耗 + 本月缓存
                prev = inv[(a,m,t-1)] if t > T[0] else 0
                P += prev + x[(a,m,t)] == x[(b,m,t)] + inv[(a,m,t)], f"flow_{a}_{m}_{t}"
        for a in S[:-1]:
            for t in T:
                if m == M[-1]: P += pulp.lpSum(inv[(a,mm,t)] for mm in M) <= cf.buffer_cap(d, a), f"buf_{a}_{t}"
    for s in S:
        n = range(ni[s])
        if util_cap:
            for t in T:
                P += pulp.lpSum(x[(s,m,t)] for m in M) <= util_cap * pulp.lpSum(cf.capacity(d,s,o(s,i),k,t)*Y(s,i,k,t) for i in n for k in K) \
                     + pulp.lpSum(cf.ot_units(d,s,o(s,i),t,ot[(s,i,t)]+otx[(s,i,t)]) for i in n), f"util_{s}_{t}"
        if head_change is not None or head_up is not None or head_dn is not None:
            hd = {t: pulp.lpSum((o(s,i)["heads"]+cf.indirect_heads(d,s,o(s,i)))*k*Y(s,i,k,t) for i in n for k in K) for t in T}
            up = head_change if head_up is None else head_up
            dn = head_change if head_dn is None else head_dn
            for t in T[1:]:
                if up is not None: P += hd[t] - hd[t-1] <= up * hd[t-1], f"hup_{s}_{t}"
                if dn is not None: P += hd[t-1] - hd[t] <= dn * hd[t-1], f"hdn_{s}_{t}"
        if jph_step:
            lvl = {t: pulp.lpSum(i * Y(s,i,k,t) for i in n for k in K) for t in T}
            for t in T[1:]:
                P += lvl[t] - lvl[t-1] <= 1, f"jstep_up_{s}_{t}"
                P += lvl[t-1] - lvl[t] <= 1, f"jstep_dn_{s}_{t}"
        if shift_quarter:
            for t in T:
                if t - 1 != T[0] - 1 and (t - T[0]) % 3:
                    for k in K:
                        P += pulp.lpSum(Y(s,i,k,t) for i in n) == pulp.lpSum(Y(s,i,k,t-1) for i in n), f"shq_{s}_{k}_{t}"
    # ===== v5：加权目标（成本/稳定/交付/人力）—— 权重项单列为"权重:*"科目，不计入运营成本 =====
    if weights:
        g = d["g"]
        for s in S:
            n = range(ni[s])
            hd = {t: pulp.lpSum((o(s,i)["heads"]+cf.indirect_heads(d,s,o(s,i)))*k*Y(s,i,k,t) for i in n for k in K) for t in T}
            if weights.get("stab"):
                dev = V(f"dev_{s}", [(t,) for t in T[1:]], lowBound=0)
                for t in T[1:]:
                    P += dev[(t,)] >= hd[t] - hd[t-1]; P += dev[(t,)] >= hd[t-1] - hd[t]
                add("权重:稳定", weights["stab"] * g.get("lam_head_change", 3000.0) * pulp.lpSum(dev.values()))
            if weights.get("labor"):
                add("权重:人力", weights["labor"] * g.get("lam_head_month", 1000.0) * pulp.lpSum(hd.values()))
        if weights.get("deliv"):
            add("权重:交付", weights["deliv"] * g.get("lam_backlog", 5000.0) * pulp.lpSum(bl.values()))
        if weights.get("cost", 1.0) != 1.0:
            raise ValueError("成本权重固定为 1（其余权重相对成本设置）")
        P.setObjective(pulp.lpSum(acc.values()))
    # ===== v5：no-good 切割（前三备选）：与已有方案至少 cut_min_diff 个车间×月的模式不同 =====
    for j, keys in enumerate(cuts or []):
        P += pulp.lpSum(y[k] for k in keys if k in y) <= len(keys) - cut_min_diff, f"nogood_{j}"
    if fix_y:
        for key, val in fix_y.items():
            if key in y: y[key].lowBound = y[key].upBound = val
    return P, dict(acc=acc, otx=otx, bl=bl, y=y, ot=ot, x=x, short=short, inv=inv, trips=trips, trips_in=trips_in,
                   ship=ship, fginv=fginv, on=on, st=st, co2over=co2over,
                   calloff=calloff, line_inv=line_inv, onc=onc, ev=ev, sdo=sdo, bw=bw, swv=swv, jlost=lost)
def solve(P, d):
    gap = d["g"].get("mip_rel_gap", 1e-4); th = int(d["g"].get("threads", 0)) or None
    s = pulp.HiGHS(msg=False, timeLimit=d["g"]["solver_time_limit"], gapRel=gap, threads=th) if "HiGHS" in pulp.listSolvers(True) else pulp.PULP_CBC_CMD(msg=False, timeLimit=int(d["g"]["solver_time_limit"]), gapRel=gap)
    P.solve(s); return pulp.LpStatus[P.status], pulp.value(P.objective)
