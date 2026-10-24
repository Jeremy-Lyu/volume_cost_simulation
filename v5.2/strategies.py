"""策略对比 + 蒙特卡洛压力测试（示例数据）"""
import copy, os, random, statistics as stt, data_loader as dl, engine, report as rp
from scenarios import apply_knobs
OUT = os.path.join(os.path.dirname(__file__), "output")
def run(d, **kw):
    return engine.solved(d, **kw)
def metrics(name, d, res):
    st, obj, plan, cost, out, sh, _ = res
    swings = []
    for s in d["shops"]:
        h = [r["heads"] for r in plan if r["shop"] == s]; swings.append(max(abs(h[i]-h[i-1])/max(h[i-1],1) for i in range(1, len(h))))
    kp = rp.kpis(d, res[6], plan, cost, out, obj); assert not rp.selfcheck(d, res[6], obj)
    return dict(策略=name, 状态=st, 总成本_万元=round(obj/1e4), 单车_元=round(kp["单车成本"]), 加班_万元=round((cost["加班"]+cost.get("超限加班溢价",0))/1e4),
                加班h=round(kp["加班h"]), 超限加班h=round(kp["超限加班h"]), 延期台月=round(kp["延期台月"]), 平均缓存台=round(kp["平均缓存"]),
                最大人数月波动=f"{max(swings):.0%}", 平均利用率=f"{stt.mean(r['util'] for r in plan):.1%}", 缺口=round(sh),
                缺口惩罚_万元=round(cost["缺口惩罚(流失)"]/1e4), 不含惩罚成本_万元=round((obj-cost["缺口惩罚(流失)"])/1e4))
STRAT = {"成本优先": ({}, {}),
         "稳定优先": ({"jph_step": True, "shift_quarter": True, "util_cap": 0.9}, {"ot": 24}),
         "保人力(人数月变化≤5%)": ({"head_change": 0.05}, {}),
         "压力:需求+20% 低惩罚(3千/台)": ({}, {"demand": 1.2, "pen": 3000}),
         "压力:需求+20% 保交付(20万/台)": ({}, {"demand": 1.2, "pen": 200000})}
def prep(base, mod):
    d = copy.deepcopy(base)
    if "ot" in mod:
        dl.set_ot_cap(d, mod["ot"])
    if "demand" in mod: d["demand"] = {k: v*mod["demand"] for k, v in d["demand"].items()}
    if "pen" in mod: d["g"]["shortage_penalty"] = mod["pen"]
    return d
def monte_carlo(base, plans, n=20, spread=0.08, seed=7):
    """固定各策略的 JPH×班次方案，只让加班/产量/缓存重新优化，抽样需求 ±8%（按月独立）"""
    rnd = random.Random(seed); samples = [{t: rnd.uniform(1-spread, 1+spread) for t in base["months"]} for _ in range(n)]
    rows = []
    for name, fy in plans.items():
        costs, shorts, delays = [], [], []
        for f in samples:
            d = copy.deepcopy(base); d["demand"] = {k: v*f[k[0]] for k, v in d["demand"].items()}
            st, obj, plan, cost, out, sh, _ = run(d, fix_y=fy); costs.append((obj-cost["缺口惩罚(流失)"])/1e4); shorts.append(sh)
            delays.append(rp.kpis(d, _, plan, cost, out, obj)["延期台月"])
        cs = sorted(costs); rows.append(dict(方案=name, 样本数=n, 平均成本_万元=round(stt.mean(costs)), P90成本_万元=round(cs[int(0.9*n)-1]),
                     平均缺口=round(stt.mean(shorts)), 最大缺口=round(max(shorts)), 有缺口样本占比=f"{sum(s>0.5 for s in shorts)/n:.0%}", 平均延期台月=round(stt.mean(delays))))
        print(rows[-1])
    return rows
JOINT = (("demand_all", 0.9, 1.1), ("elec", 0.9, 1.1), ("wage", 0.97, 1.03), ("avail", 0.9, 1.0))
def joint_factors(n=20, seed=7):
    """需求、电价、工资、开动率一起抽。固定种子。这只是样本，不是决策卡上的概率。"""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        row = {"样本": i + 1}
        for key, lo, hi in JOINT:
            row[key] = round(rnd.uniform(lo, hi), 4)
        rows.append(row)
    return rows
def joint_sample(base, plan, n=20, seed=7):
    """班次锁定在传入方案上。结果写入策略输出，不进决策卡。"""
    rows = []
    for f in joint_factors(n, seed):
        knobs = {"demand_all": f["demand_all"], "elec": f["elec"], "wage": f["wage"],
                 "avail": {f"ALL|{t}": f["avail"] for t in base["months"]}}
        d = apply_knobs(base, knobs)
        st, obj, plan_r, cost, out, sh, v = run(d, fix_y=plan)
        rows.append(dict(样本=f["样本"], demand_all=f["demand_all"], elec=f["elec"], wage=f["wage"], avail=f["avail"],
                         状态=st, 不含惩罚成本_万元=round((obj - cost["缺口惩罚(流失)"]) / 1e4), 缺口=round(sh)))
    return rows
if __name__ == "__main__":
    base = dl.load(); rows, plans = [], {}
    for name, (kw, mod) in STRAT.items():
        d = prep(base, mod); res = run(d, **kw); rows.append(metrics(name, d, res)); print(rows[-1])
        if name in ("成本优先", "稳定优先"): plans[name] = {k: round(var.value()) for k, var in res[6]["y"].items()}
        rp.write_csv(os.path.join(OUT, f"plan_策略_{name.split('(')[0].replace(':','_')}.csv"), res[2])
    rp.write_csv(os.path.join(OUT, "strategy_summary.csv"), rows)
    mc = monte_carlo(base, plans); rp.write_csv(os.path.join(OUT, "montecarlo_summary.csv"), mc)
    if "成本优先" in plans:
        js = joint_sample(base, plans["成本优先"])
        rp.write_csv(os.path.join(OUT, "joint_sample.csv"), js)
        print("联合抽样", len(js), "行 → output/joint_sample.csv")
