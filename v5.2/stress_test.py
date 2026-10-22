"""压力测试（示例数据）：(a) 场景库 (b) 焊装停线天数扫描 (c) 需求上限"""
import os, data_loader as dl, model_builder as mb, report as rp, cost_functions as cf
from scenarios import apply_knobs, load_library
OUT = os.path.join(os.path.dirname(__file__), "output")
def solve(d, tl=30):
    d["g"]["solver_time_limit"] = tl; P, v = mb.build(d); st, obj = mb.solve(P, d)
    plan, cost, out, sh = rp.extract(d, v); return st, obj, plan, cost, out, sh, v
def maxcap(d, s, t):  # 该车间该月最大可能产能（最高档 × 三班 × 加班上限）
    return max(cf.capacity(d, s, o, k, t) + cf.ot_units(d, s, o, t, d["g"]["ot_hard_cap_per_head_month"] * k) for o in d["jph"][s] for k in d["shift"])
def bottleneck(d, plan, v):
    sm = {}
    for m in d["models"]:
        for t in d["months"]: sm[t] = sm.get(t, 0) + v["bl"][(m, t)].value()   # v4：缺口=期末积压（延期+流失）
    months = [t for t in d["months"] if sm[t] > 0.5] or d["months"]
    slack = {s: sum(maxcap(d, s, t) - next(r["volume"] for r in plan if r["shop"] == s and r["month"] == t) for t in months) / len(months) for s in d["shops"]}
    b = min(slack, key=slack.get); return b, [t for t in d["months"] if sm[t] > 0.5]
def row(name, d, res, extra=None):
    st, obj, plan, cost, out, sh, v = res; b, sm = bottleneck(d, plan, v)
    three = sum(1 for r in plan if r["shifts"] == 3)
    kp = rp.kpis(d, v, plan, cost, out, obj); assert not rp.selfcheck(d, v, obj)
    r = dict(场景=name, 状态=st, 总成本_万元=round(obj/1e4), 运营成本_万元=round(kp["运营成本"]/1e4), 单车_元=round(kp["单车成本"]),
             产量=round(out), 流失=round(sh), 延期台月=round(kp["延期台月"]), 超限加班h=round(kp["超限加班h"]), 停线车间月=kp["停线车间月"], 积压月份="/".join(map(str, sm)) or "-", 瓶颈车间=b, 加班_万元=round(cost["加班"]/1e4), 三班车间月数=three)
    r.update(extra or {}); print(r); return r
if __name__ == "__main__":
    base = dl.load()
    # (a) 场景库
    rows = [row("基准", base, solve(apply_knobs(base, {})), {"类别": "-", "说明": "无旋钮"})]
    for sc in load_library():
        d = apply_knobs(base, sc["knobs"]); rows.append(row(sc["name"], d, solve(d), {"类别": sc["category"], "说明": sc["description"]}))
    rp.write_csv(os.path.join(OUT, "stress_library.csv"), rows)
    # (b) 焊装 6 月停线天数扫描
    sw = []
    for n in [0, 2, 4, 6, 8, 10]:
        d = apply_knobs(base, {"down": {"BIW|6": n}}); res = solve(d); p = {(r["shop"], r["month"]): r for r in res[2]}
        b6 = p[("BIW", 6)]; b5 = p[("BIW", 5)]
        sw.append(row(f"焊装6月停线{n}天", d, res, {"停线天数": n, "焊装6月方案": f"{int(b6['jph'])}x{b6['shifts']}", "焊装6月加班h": b6["ot_hours"],
                       "焊装6月产量": b6["volume"], "焊装5月方案": f"{int(b5['jph'])}x{b5['shifts']}", "焊装5月产量": b5["volume"]}))
    rp.write_csv(os.path.join(OUT, "stress_downtime_sweep.csv"), sw)
    # (c) 需求上限（高惩罚，找第一次缺口）
    cl = []
    for f in [1.0, 1.1, 1.2, 1.3, 1.35, 1.4, 1.45, 1.5]:
        d = apply_knobs(base, {"demand_all": f}); d["g"]["shortage_penalty"] = 200000
        cl.append(row(f"需求×{f}", d, solve(d), {"需求系数": f}))
    rp.write_csv(os.path.join(OUT, "stress_demand_ceiling.csv"), cl)
