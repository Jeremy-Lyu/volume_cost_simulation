"""v5 策略生成与推荐：加权目标扫描 → 帕累托前沿 → 规则推荐（带理由）→ 前三备选（no-good 切割）
权重（相对成本=1）：stab 人数变化（×lam_head_change 元/人，⚠3000）、deliv 积压（×lam_backlog 元/台·月，⚠5000）、labor 总人数（×lam_head_month，⚠1000）
管理层阈值（⚠ 示例）：THRESH"""
import copy, itertools, os
import engine as en
THRESH = dict(最大人数月波动=0.30, 延期台月=800, 流失台=0, 成本上浮=0.05)
GRID = [dict(stab=s, deliv=b) for s, b in itertools.product([0, 0.5, 1, 2, 4], [0, 1, 3])] + [dict(labor=1), dict(stab=1, deliv=1, labor=1)]
def wname(w): return "成本优先" if not any(w.values()) else "·".join(f"{dict(stab='稳定',deliv='交付',labor='人力')[k]}{v:g}" for k, v in w.items() if v)
def metrics(r):
    k = r["kpi"]; return dict(方案=r["name"], 运营成本_万元=round(k["运营成本"]/1e4), 单车_元=round(k["单车成本"]), 人数最大月波动=round(k["人数最大月波动"], 3),
                            人数变化合计=round(k["人数变化合计"]), 延期台月=round(k["延期台月"]), 流失台=round(k["流失台"]), 加班h=round(k["加班h"]), 超限加班h=round(k["超限加班h"]))
def pareto(rows, keys=("运营成本_万元", "人数变化合计", "延期台月")):
    def dom(a, b): return all(a[k] <= b[k] for k in keys) and any(a[k] < b[k] for k in keys)
    return [r for r in rows if r["流失台"] == 0 and not any(dom(o, r) for o in rows if o is not r and o["流失台"] == 0)]
def sweep(base, procs=6):
    d = copy.deepcopy(base); d["g"]["solver_time_limit"] = 40; d["g"]["mip_rel_gap"] = 2e-3
    res = en.run_many([(copy.deepcopy(d), wname(w), dict(weights=w)) for w in GRID], procs)
    rows = [dict(metrics(r), **{f"w_{k}": v for k, v in w.items()}) for r, w in zip(res, GRID)]
    for r in rows: r["帕累托"] = ""
    for r in pareto(rows): r["帕累托"] = "★"
    return rows, res
def recommend(rows, th=THRESH):
    base = next(r for r in rows if r["方案"] == "成本优先"); cap = base["运营成本_万元"] * (1 + th["成本上浮"])
    feas = [r for r in rows if r["帕累托"] and r["人数最大月波动"] <= th["最大人数月波动"] and r["延期台月"] <= th["延期台月"]
            and r["流失台"] <= th["流失台"] and r["运营成本_万元"] <= cap]
    if feas:
        rec = min(feas, key=lambda r: r["运营成本_万元"]); flag = "满足全部阈值"
    else:
        def viol(r): return max(0, r["人数最大月波动"]/th["最大人数月波动"]-1) + max(0, r["延期台月"]/max(th["延期台月"],1)-1) + max(0, r["运营成本_万元"]/cap-1)
        rec = min([r for r in rows if r["帕累托"]], key=viol); flag = "没有方案满足全部阈值，推荐最接近者"
    why = (f"推荐「{rec['方案']}」（{flag}）：运营成本 {rec['运营成本_万元']:,} 万元，比成本优先 {rec['运营成本_万元']-base['运营成本_万元']:+,} 万元；"
           f"人数最大月波动 {base['人数最大月波动']:.0%} → {rec['人数最大月波动']:.0%}；延期 {base['延期台月']} → {rec['延期台月']} 台·月；流失 {rec['流失台']} 台。"
           f"阈值（⚠示例）：波动≤{th['最大人数月波动']:.0%}、延期≤{th['延期台月']}台·月、无流失、成本≤成本优先+{th['成本上浮']:.0%}；"
           f"候选 {len(rows)} 个，帕累托前沿 {sum(1 for r in rows if r['帕累托'])} 个，满足阈值 {len(feas)} 个。")
    return rec, why
def top3(base, w, procs=1):
    d = copy.deepcopy(base); d["g"]["solver_time_limit"] = 60; d["g"]["mip_rel_gap"] = 2e-3; out, cuts = [], []
    for j in range(3):
        r = en.solve_case(copy.deepcopy(d), f"备选{j+1}", weights=w, cuts=[tuple(c) for c in cuts], cut_min_diff=2)
        out.append(r); cuts.append(en.chosen(r["y"]))
    return out
def mode_diff(plan_a, plan_b):
    a = {(p["shop"], p["month"]): f"{int(p['jph'])}x{p['shifts']}" for p in plan_a}
    return "; ".join(f"{s}-{t}月 {a[(s,t)]}→{v}" for (s, t), v in ((k, f"{int(p['jph'])}x{p['shifts']}") for k, p in ((((p["shop"], p["month"])), p) for p in plan_b)) if a[(s, t)] != v) or "无"
