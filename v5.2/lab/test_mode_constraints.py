"""测试可选的模式切换约束（示例数据）"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import data_loader as dl, engine
d = dl.load()
for name, kw in {"基准(无切换约束)": {}, "JPH相邻月最多变一档": {"jph_step": True}, "班次按季度固定": {"shift_quarter": True}, "两者都加": {"jph_step": True, "shift_quarter": True}}.items():
    st, obj, plan, cost, out, sh, v = engine.solved(d, **kw)
    print(name, st, "总成本", round(obj/1e4), "万元 单车", round(obj/out), "加班", round(cost["加班"]/1e4), "缓存", round(cost["缓存持有"]/1e4), "缺口", round(sh))
    for s in d["shops"]: print("  ", s, "/".join(f"{int(r['jph'])}x{r['shifts']}" for r in plan if r["shop"] == s))
