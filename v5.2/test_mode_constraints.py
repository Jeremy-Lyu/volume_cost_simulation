"""测试可选的模式切换约束（示例数据）"""
import data_loader as dl, model_builder as mb, report as rp
d = dl.load()
for name, kw in {"基准(无切换约束)": {}, "JPH相邻月最多变一档": {"jph_step": True}, "班次按季度固定": {"shift_quarter": True}, "两者都加": {"jph_step": True, "shift_quarter": True}}.items():
    P, v = mb.build(d, **kw); st, obj = mb.solve(P, d); plan, cost, out, sh = rp.extract(d, v)
    print(name, st, "总成本", round(obj/1e4), "万元 单车", round(obj/out), "加班", round(cost["加班"]/1e4), "缓存", round(cost["缓存持有"]/1e4), "缺口", round(sh))
    for s in d["shops"]: print("  ", s, "/".join(f"{int(r['jph'])}x{r['shifts']}" for r in plan if r["shop"] == s))
