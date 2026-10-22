"""块11：场景模拟——基准 + 需求±10% + 电价+20% + 工资+5%"""
import os, data_loader as dl, model_builder as mb, report as rp
OUT = os.path.join(os.path.dirname(__file__), "output")
SCEN = {"基准": {}, "需求+10%": {"demand": 1.1}, "需求-10%": {"demand": 0.9}, "电价+20%": {"elec": 1.2}, "工资+5%": {"wage": 1.05}}
def main():
    base = dl.load(); summ = []
    for name, kw in SCEN.items():
        d = dl.scenario(base, **kw); P, v = mb.build(d); st, obj = mb.solve(P, d)
        plan, cost, out, sh = rp.extract(d, v)
        err = rp.selfcheck(d, v, obj); assert not err, f"{name} 守恒自检失败: {err}"
        kp = rp.kpis(d, v, plan, cost, out, obj)
        rp.write_csv(os.path.join(OUT, f"plan_{name}.csv"), plan)
        rp.write_csv(os.path.join(OUT, f"cost_{name}.csv"), [{"科目": k, "金额_元": round(x)} for k, x in cost.items()])
        shifts = {s: "/".join(f"{int(r['jph'])}x{r['shifts']}" for r in plan if r["shop"] == s) for s in d["shops"]}
        summ.append(dict(场景=name, 状态=st, 总成本_万元=round(obj/1e4), 运营成本_万元=round(kp["运营成本"]/1e4), 产量=round(out), 缺口=round(sh),
                         延期台月=round(kp["延期台月"]), 流失台=round(kp["流失台"]), 加班h=round(kp["加班h"]), 超限加班h=round(kp["超限加班h"]),
                         平均缓存台=round(kp["平均缓存"]), 停线车间月=kp["停线车间月"],
                         单车成本_元=round(kp["单车成本"]), 加班成本_万元=round((cost["加班"]+cost.get("超限加班溢价",0))/1e4), 能源_万元=round(sum(x for kk, x in cost.items() if kk.startswith(("能源", "启停", "需量")))/1e4), **{f"{s}_JPHx班": shifts[s] for s in d["shops"]}))
        print(name, st, summ[-1]["总成本_万元"], "万元, 单车", summ[-1]["单车成本_元"])
    rp.write_csv(os.path.join(OUT, "scenario_summary.csv"), summ)
    import golden; golden.check(summ)
    with open(os.path.join(OUT, "results_summary.md"), "w", encoding="utf-8") as f:
        f.write("# 原型运行结果（示例数据，非真实数据）\n\n| 场景 | 状态 | 总成本(万元) | 年产量 | 缺口 | 单车成本(元) | 加班(万元) | 能源(万元) |\n|:--|:--|--:|--:|--:|--:|--:|--:|\n")
        for r in summ: f.write(f"| {r['场景']} | {r['状态']} | {r['总成本_万元']:,} | {r['产量']:,} | {r['缺口']} | {r['单车成本_元']:,} | {r['加班成本_万元']} | {r['能源_万元']} |\n")
        f.write("\n## 各车间每月 JPH×班次（1–12月）\n\n")
        for r in summ:
            f.write(f"**{r['场景']}**\n\n"); [f.write(f"- {s}: {r[s+'_JPHx班']}\n") for s in base["shops"]]; f.write("\n")
if __name__ == "__main__": main()
