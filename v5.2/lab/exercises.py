"""练习：在内存中改参数后重新求解，与基准对比（示例数据）"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import copy, os, data_loader as dl, engine, report as rp
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
def e1(d):  # 加班上限 36 → 60 小时/月（所有车间）
    dl.set_ot_cap(d, 60)
def e2(d):  # 需求+10% 且 夜班补贴 800 → 0
    d["demand"] = {k: v*1.1 for k, v in d["demand"].items()}; d["g"]["night_allowance_per_head_night"] = 0
def e3(d):  # 夏季峰电：7、8 月电价 ×1.5
    d["elec_month_factor"] = {7: 1.5, 8: 1.5}
def e4(d):  # 10 月需求冲击 +25%
    d["demand"] = {k: v*(1.25 if k[0] == 10 else 1) for k, v in d["demand"].items()}
def e5(d):  # 对照组：仅需求+10%（与 e2 比）
    d["demand"] = {k: v*1.1 for k, v in d["demand"].items()}
EX = {"练习0_基准": lambda d: None, "练习1_加班上限60h": e1, "练习2_需求+10%无夜班补贴": e2, "练习2对照_需求+10%": e5, "练习3_7-8月峰电x1.5": e3, "练习4_10月需求+25%": e4}
if __name__ == "__main__":
    base = dl.load(); rows = []
    for n, f in EX.items():
        d = copy.deepcopy(base); f(d)
        st, obj, plan, cost, out, sh, v = engine.solved(d)
        rp.write_csv(os.path.join(OUT, f"plan_{n}.csv"), plan)
        js = {s: "/".join(f"{int(r['jph'])}x{r['shifts']}" for r in plan if r["shop"] == s) for s in d["shops"]}
        rows.append(dict(练习=n, 状态=st, 总成本_万元=round(obj/1e4), 产量=round(out), 缺口=round(sh), 单车_元=round(obj/out),
                         加班_万元=round(cost["加班"]/1e4), 能源_万元=round((cost["能源固定"]+cost["能源变动"])/1e4), 缓存持有_万元=round(cost["缓存持有"]/1e4), **{s: js[s] for s in d["shops"]}))
        print(rows[-1])
    rp.write_csv(os.path.join(OUT, "exercises_summary.csv"), rows)
