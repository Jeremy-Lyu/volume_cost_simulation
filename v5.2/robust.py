"""v5 稳健方案：基于情景的两阶段随机规划
第一阶段（所有情景共用）：每车间每月 JPH档×班次 y；第二阶段（每情景各自）：加班 ot/otx、产量 x、缓存 inv、积压 bl、流失 short
模式 mode：
  "mean"   最小化 固定成本 + 情景平均可变成本
  "cvar"   最小化 固定成本 + (1−λ)·平均 + λ·CVaR_α（最坏 1−α 情景的平均可变成本）
  "chance" 平均目标 + 至少 α 比例情景不流失（二元 z 标记允许流失的情景）
仅支持基础口径（无 v2/v3 可选扩展表）；示例数据"""
import copy, math, pulp
import cost_functions as cf
def scen_data(d, sc):
    e = dict(d); e["demand"] = sc["demand"]; e["avail"] = sc.get("avail", {}); return e
def build_robust(d, scens, mode="mean", alpha=0.9, lam=0.5):
    for k in ("lanes", "line_supply", "ship", "margin", "chg", "rework"):
        assert not d.get(k), f"robust 仅支持基础口径（检测到可选扩展 {k}）"
    S, M, T = d["shops"], d["models"], d["months"]; K = sorted(d["shift"]); N = len(scens)
    ni = {s: len(d["jph"][s]) for s in S}; o = lambda s, i: d["jph"][s][i]
    P = pulp.LpProblem("robust", pulp.LpMinimize)
    C = [(s, i, k, t) for s in S for i in range(ni[s]) for k in K for t in T if k > 0 or i == 0]
    y = pulp.LpVariable.dicts("y", C, cat="Binary"); Y = lambda s, i, k, t: y.get((s, i, k, t), 0)
    first = pulp.lpSum(sum(cf.fixed_breakdown(d, s, o(s, i), k, t).values()) * y[(s, i, k, t)] for (s, i, k, t) in C) \
        + sum(d["shop"][s]["oh_fixed_month"] for s in S) * len(T)
    for s in S:
        for t in T: P += pulp.lpSum(Y(s, i, k, t) for i in range(ni[s]) for k in K) == 1
    rc, lost = [], []
    for w, sc in enumerate(scens):
        e = scen_data(d, sc)
        I3 = [(s, i, t) for s in S for i in range(ni[s]) for t in T]
        ot = pulp.LpVariable.dicts(f"ot{w}", I3, lowBound=0); otx = pulp.LpVariable.dicts(f"otx{w}", I3, lowBound=0)
        x = pulp.LpVariable.dicts(f"x{w}", [(s, m, t) for s in S for m in M for t in T], lowBound=0)
        inv = pulp.LpVariable.dicts(f"inv{w}", [(s, m, t) for s in S[:-1] for m in M for t in T], lowBound=0)
        bl = pulp.LpVariable.dicts(f"bl{w}", [(m, t) for m in M for t in T], lowBound=0)
        for s in S:
            n = range(ni[s])
            for t in T:
                for i in n:
                    kk = pulp.lpSum(k * Y(s, i, k, t) for k in K)
                    P += ot[(s, i, t)] <= e["shop"][s]["ot_max_hours_month"] * kk
                    P += otx[(s, i, t)] <= (e["g"]["ot_hard_cap_per_head_month"] - e["shop"][s]["ot_max_hours_month"]) * kk
                P += pulp.lpSum(x[(s, m, t)] for m in M) <= pulp.lpSum(cf.capacity(e, s, o(s, i), k, t) * Y(s, i, k, t) for i in n for k in K) \
                    + pulp.lpSum(cf.ot_units(e, s, o(s, i), t, ot[(s, i, t)] + otx[(s, i, t)]) for i in n)
                for m in M: P += x[(s, m, t)] <= e["cap"][(s, m, t)]
        for m in M:
            for t in T:
                pb = bl[(m, t - 1)] if t > T[0] else 0
                P += pb + e["demand"][(t, m)] == x[(S[-1], m, t)] + bl[(m, t)]
                for a, b in zip(S[:-1], S[1:]):
                    prev = inv[(a, m, t - 1)] if t > T[0] else 0
                    P += prev + x[(a, m, t)] == x[(b, m, t)] + inv[(a, m, t)]
        for a in S[:-1]:
            for t in T: P += pulp.lpSum(inv[(a, m, t)] for m in M) <= cf.buffer_cap(e, a)
        cost = []
        for (s, i, t) in I3:
            cost += [(cf.ot_labor_per_hour(e, s, o(s, i)) + o(s, i)["kw"] * cf.price(e, t)) * (ot[(s, i, t)] + otx[(s, i, t)]),
                     cf.ot_excess_per_hour(e, s, o(s, i)) * otx[(s, i, t)]]
        cost += [sum(cf.var_parts(e, s, t).values()) * x[(s, m, t)] for (s, m, t) in x]
        cost += [e["shop"][s]["hold_cost_per_unit_month"] * inv[(s, m, t)] for (s, m, t) in inv]
        cost += [e["g"]["backlog_cost_per_unit_month"] * bl[(m, t)] for m in M for t in T[:-1]]
        lw = pulp.lpSum(bl[(m, T[-1])] for m in M); lost.append(lw)
        cost += [e["g"]["shortage_penalty"] * lw]
        rc.append(pulp.lpSum(cost))
    mean = pulp.lpSum(rc) * (1.0 / N)
    if mode == "cvar":
        eta = pulp.LpVariable("eta"); u = pulp.LpVariable.dicts("u", range(N), lowBound=0)
        for w in range(N): P += u[w] >= rc[w] - eta
        P += first + (1 - lam) * mean + lam * (eta + pulp.lpSum(u.values()) * (1.0 / (N * (1 - alpha))))
    else:
        P += first + mean
        if mode == "chance":
            z = pulp.LpVariable.dicts("z", range(N), cat="Binary"); big = sum(sum(sc["demand"].values()) for sc in scens)
            for w in range(N): P += lost[w] <= big * z[w]
            P += pulp.lpSum(z.values()) <= math.floor((1 - alpha) * N)
    return P, y
def solve_robust(d, scens, mode="mean", alpha=0.9, lam=0.5, time_limit=180):
    P, y = build_robust(d, scens, mode, alpha, lam)
    sol = pulp.HiGHS(msg=False, timeLimit=time_limit, gapRel=d["g"].get("robust_gap", 0.002)) if "HiGHS" in pulp.listSolvers(True) \
        else pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=0.002)
    P.solve(sol)
    return pulp.LpStatus[P.status], pulp.value(P.objective), {k: round(v.value()) for k, v in y.items()}
