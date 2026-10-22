"""v5 新模块测试（示例数据，用 3 个月子集保证速度）"""
import copy, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import data_loader as dl, engine as en, forecast as fc, robust as rb, limits, strategy_v5 as sv, outputs_v5 as ov
from scenarios import apply_knobs
def small(n=3):
    d = dl.load(); d["months"] = d["months"][:n]; d["demand"] = {k: v for k, v in d["demand"].items() if k[0] in d["months"]}; d["g"]["solver_time_limit"] = 30; d["g"]["mip_rel_gap"] = 1e-3; return d
@pytest.fixture(scope="module")
def d(): return small()
def test_cache_hit(d):
    r1 = en.solve_case(copy.deepcopy(d), "a"); t = time.time(); r2 = en.solve_case(copy.deepcopy(d), "b")
    assert r2["cached"] and time.time() - t < 1 and abs(r1["obj"] - r2["obj"]) < 1e-6
def test_hash_ignores_threads(d):
    e = copy.deepcopy(d); e["g"]["threads"] = 1; assert en.phash(d, {}) == en.phash(e, {})
def test_weights_not_in_opcost(d):
    r0 = en.solve_case(copy.deepcopy(d), "c"); rw = en.solve_case(copy.deepcopy(d), "w", weights=dict(stab=2, deliv=1))
    wt = sum(v for k, v in rw["cost"].items() if k.startswith("权重:"))
    assert wt >= -1e-6 and abs(rw["obj"] - wt - (rw["kpi"]["运营成本"] + rw["cost"].get("缺口惩罚(流失)", 0) - (-rw["cost"].get("−边际贡献", 0)))) < 1.0
    assert rw["kpi"]["运营成本"] >= r0["kpi"]["运营成本"] - 1e-3 * abs(r0["kpi"]["运营成本"])   # 加权方案运营成本不低于成本优先（gap 内）
    assert rw["kpi"]["人数变化合计"] <= r0["kpi"]["人数变化合计"] + 1e-6 or rw["kpi"]["延期台月"] <= r0["kpi"]["延期台月"] + 1e-6
def test_nogood_alternatives_differ(d):
    a = en.solve_case(copy.deepcopy(d), "n1"); ka = en.chosen(a["y"])
    b = en.solve_case(copy.deepcopy(d), "n2", cuts=[tuple(ka)], cut_min_diff=2)
    assert len(set(ka) - set(en.chosen(b["y"]))) >= 1 and b["obj"] >= a["obj"] - 1e-3 * abs(a["obj"])
def test_forecast_quantiles_ordered(d):
    rows = fc.quantile_table(dl.load())
    assert rows and all(r["P10"] <= r["P50"] <= r["P90"] for r in rows)
    sc = fc.sample_scenarios(d, 5, seed=1); assert len(sc) == 5 and all(v > 0 for s in sc for v in s["demand"].values())
    assert fc.sample_scenarios(d, 3, seed=9)[0] == fc.sample_scenarios(d, 3, seed=9)[0]      # 同种子可复现
def test_robust_small(d):
    sc = fc.sample_scenarios(d, 3, seed=3)
    st, obj, y = rb.solve_robust(d, sc, mode="mean", time_limit=60)
    assert st in ("Optimal", "Not Solved") or "ptimal" in st
    for s in d["shops"]:                                   # 第一阶段：每车间每月恰好一个模式
        for t in d["months"]: assert sum(v for (a, i, k, tt), v in y.items() if a == s and tt == t) == 1
    r = en.solve_case(copy.deepcopy(d), "fix", fix_y=y); assert r["status"] == "Optimal"
def test_limit_monotone(d):
    mk = lambda f: apply_knobs(d, {"demand_all": 1 + f})
    br = limits.find_limits([("需求", mk, limits.ok_delivery, 0.0, 0.8)], grid=3, refine=1, procs=1)
    a, b, _ = br["需求"]
    if b is not None:
        assert limits.ok_delivery(en.solve_case(mk(a), "lo"), mk(a)) and not limits.ok_delivery(en.solve_case(mk(b), "hi"), mk(b))
def test_shadow_price_sign(d):
    r0 = en.solve_case(copy.deepcopy(d), "sp0")
    e = copy.deepcopy(d); e["g"]["ot_hard_cap_per_head_month"] += 10
    for s in e["shop"]: e["shop"][s]["buffer_cap"] += 500
    r1 = en.solve_case(e, "sp1", fix_y=r0["y"])
    assert r1["kpi"]["运营成本"] <= r0["kpi"]["运营成本"] + 1.0        # 放宽资源不会更贵
def test_recommend_and_pareto():
    rows = [dict(方案="成本优先", 运营成本_万元=100, 人数变化合计=50, 延期台月=900, 流失台=0, 人数最大月波动=0.6),
            dict(方案="稳定1", 运营成本_万元=102, 人数变化合计=20, 延期台月=500, 流失台=0, 人数最大月波动=0.2),
            dict(方案="差", 运营成本_万元=110, 人数变化合计=60, 延期台月=950, 流失台=0, 人数最大月波动=0.7)]
    for r in rows: r["帕累托"] = ""
    for r in sv.pareto(rows): r["帕累托"] = "★"
    assert [r["方案"] for r in rows if r["帕累托"]] == ["成本优先", "稳定1"]
    rec, why = sv.recommend(rows); assert rec["方案"] == "稳定1" and "推荐" in why
def test_excel_and_waterfall(tmp_path, d):
    r = en.solve_case(copy.deepcopy(d), "x"); rw = en.solve_case(copy.deepcopy(d), "y", weights=dict(stab=4))
    wf = ov.waterfall(r, rw, str(tmp_path / "w.png")); assert (tmp_path / "w.png").exists()
    assert abs(sum(x["差额_万元"] for x in wf) - (rw["kpi"]["运营成本"] - r["kpi"]["运营成本"]) / 1e4) < 2 + 0.6 * 20
    ov.excel(str(tmp_path / "o.xlsx"), {"表": [dict(a=1, b=2)], "说明": ["x"]}); assert (tmp_path / "o.xlsx").exists()
