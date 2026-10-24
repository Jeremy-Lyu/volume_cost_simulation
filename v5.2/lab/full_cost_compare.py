"""全成本口径对比：基础口径(data/) vs 全成本口径(plants/FULL_COST/)
输出：成本分项对照、单车口径差、JPH×班次差异、财务口径对照表、决策留痕模板
用法：python3 make_full_cost_plant.py && python3 full_cost_compare.py
"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import os
import data_loader as dl, model_builder as mb, report as rp, cost_functions as cf
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(H, "output")
ORDER = ["物料", "人工", "福利社保", "加班", "超限加班溢价", "停线固定", "延期成本", "质量成本", "能源固定", "能源变动", "换型", "班车", "外包",
         "设备折旧", "模具摊销", "物流-成品", "物流-入厂", "碳配额购买",
         "OH", "缓存持有", "成品持有", "库存资金", "保修与碳", "缺口惩罚(流失)"]
def run(pkg):
    d = dl.load(os.path.join(H, pkg)); P, v = mb.build(d); st, obj = mb.solve(P, d)
    plan, cost, out, sh = rp.extract(d, v)
    shipped = sum(var.value() for var in v["ship"].values()) if v.get("ship") else out
    fg = sum(var.value() for var in v["fginv"].values()) if v.get("fginv") else 0.0
    mg = sum(cf.margin(d, m, t) * (v["ship"][(m,t)].value() if v.get("ship") else v["x"][(d["shops"][-1],m,t)].value())
             for m in d["models"] for t in d["months"])
    return d, st, obj, plan, cost, out, sh, shipped, fg, mg
def tc(c): return sum(v for k, v in c.items() if k != "−边际贡献")   # 成本合计（含物料，不含边际贡献）
def shifts(plan, shops):
    return "<br>".join(f"{s}: " + "/".join(f"{int(r['jph'])}x{r['shifts']}" for r in plan if r["shop"] == s) for s in shops)
def main():
    d0, st0, o0, p0, c0, out0, sh0, shp0, fg0, mg0 = run("data")
    d1, st1, o1, p1, c1, out1, sh1, shp1, fg1, mg1 = run(os.path.join("plants", "FULL_COST"))
    rows = []
    for k in ORDER:
        a, b = c0.get(k, 0), c1.get(k, 0)
        if a or b: rows.append(dict(科目=k, 基础口径_万元=round(a/1e4), 全成本口径_万元=round(b/1e4), 差异_万元=round((b-a)/1e4)))
    rows.append(dict(科目="成本合计（含常数项）", 基础口径_万元=round(tc(c0)/1e4), 全成本口径_万元=round(tc(c1)/1e4), 差异_万元=round((tc(c1)-tc(c0))/1e4)))
    rows.append(dict(科目="− 边际贡献", 基础口径_万元=0, 全成本口径_万元=round(-mg1/1e4), 差异_万元=round(-mg1/1e4)))
    rows.append(dict(科目="= 目标值（成本−边际贡献）", 基础口径_万元=round(o0/1e4), 全成本口径_万元=round(o1/1e4), 差异_万元=round((o1-o0)/1e4)))
    rp.write_csv(os.path.join(OUT, "full_cost_compare.csv"), rows)
    summary = [dict(口径="基础（可控制费）", 状态=st0, 目标值_万元=round(o0/1e4), 成本合计_万元=round(tc(c0)/1e4),
                    边际贡献_万元=0, 产量=round(out0), 发货=round(shp0), 成品库存_台月=round(fg0), 单车成本_元=round(tc(c0)/max(out0,1)), 缺口=round(sh0)),
               dict(口径="全成本（含物料等+边际贡献）", 状态=st1, 目标值_万元=round(o1/1e4), 成本合计_万元=round(tc(c1)/1e4),
                    边际贡献_万元=round(mg1/1e4), 产量=round(out1), 发货=round(shp1), 成品库存_台月=round(fg1), 单车成本_元=round(tc(c1)/max(out1,1)), 缺口=round(sh1))]
    rp.write_csv(os.path.join(OUT, "full_cost_summary.csv"), summary)
    rp.write_csv(os.path.join(OUT, "full_cost_plan.csv"), p1)
    rp.write_account_map(os.path.join(OUT, "account_map.csv"))
    print("\n=== 口径对比 ===")
    for r in summary: print(r)
    print("\n=== 成本分项（万元） ===")
    for r in rows: print(r)
    print("\n=== 全成本口径下 各车间 JPH×班次 ===")
    for s in d1["shops"]: print(" ", s, "/".join(f"{int(r['jph'])}x{r['shifts']}" for r in p1 if r["shop"] == s))
    print(f"\n对比表：output/full_cost_compare.csv ｜ 口径表：output/account_map.csv（示例数据）")
if __name__ == "__main__":
    main()
