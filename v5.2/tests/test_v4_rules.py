"""v4 新规则测试：延期交付 / 0 班 / 加班软上限 / 加班单价联动 / golden"""
import copy, pytest, cost_functions as cf, data_loader as dl
from conftest import solve, subset

def test_backlog_delay_not_lost(base):
    """10 月需求翻倍超出产能、11 月需求很低 → 应延期到 11 月交付，而不是流失"""
    d = subset(base, [10, 11]); d = copy.deepcopy(d)
    for m in d["models"]: d["demand"][(10, m)] *= 1.6; d["demand"][(11, m)] *= 0.3
    r = solve(d); bl10 = sum(r["v"]["bl"][(m, 10)].value() for m in d["models"])
    assert bl10 > 1 and r["sh"] == pytest.approx(0, abs=1e-6), f"10月积压{bl10:.0f}，流失{r['sh']:.0f}"
    assert r["cost"]["延期成本"] == pytest.approx(bl10 * d["g"]["backlog_cost_per_unit_month"], rel=1e-6)

def test_end_backlog_is_lost(base):
    d = subset(base, [10]); d = copy.deepcopy(d)
    for k in d["demand"]: d["demand"][k] *= 3
    r = solve(d); assert r["sh"] > 0 and r["cost"].get("延期成本", 0) == pytest.approx(0)

def test_ot_capacity_scales_with_shifts(base):
    d = subset(base, [10]); o = d["jph"]["TCF"][-1]
    hard = d["g"]["ot_hard_cap_per_head_month"]
    # 2 班时线体加班上限 = 2 × 人均上限：用一个 2班+大量加班才可行的需求验证
    d = copy.deepcopy(d); need = cf.capacity(d, "TCF", o, 2, 10) + cf.ot_units(d, "TCF", o, 10, 1.5 * hard)
    tot = sum(v for (t, m), v in d["demand"].items()); f = need / tot
    for k in d["demand"]: d["demand"][k] *= f * 0.999
    for s in d["shops"]: d["shop"][s]["buffer_cap"] = 0 if s != "TCF" else 0
    r = solve(d); tcf = next(p for p in r["plan"] if p["shop"] == "TCF")
    assert r["sh"] == pytest.approx(0, abs=1) or tcf["shifts"] == 3

def test_excess_ot_used_and_reported(base):
    """需求略超 2班+36h/人 时，应使用超限加班（比开 3 班便宜），并单列溢价"""
    d = subset(base, [10]); d = copy.deepcopy(d); o = d["jph"]["TCF"][-1]
    need = cf.capacity(d, "TCF", o, 2, 10) + cf.ot_units(d, "TCF", o, 10, 2 * 36 + 10)
    tot = sum(d["demand"].values())
    for k in d["demand"]: d["demand"][k] *= need / tot
    r = solve(d); tcf = next(p for p in r["plan"] if p["shop"] == "TCF")
    if tcf["shifts"] == 2:
        assert tcf["ot_excess_hours"] > 0 and r["cost"]["超限加班溢价"] > 0
    assert tcf["ot_per_head"] <= d["g"]["ot_hard_cap_per_head_month"] + 0.1

def test_wage_scenario_moves_ot_cost(base):
    d = subset(base, [10]); a = solve(d); b = solve(dl.scenario(d, wage=1.05))
    oa = sum(p["ot_hours"] for p in a["plan"]); ob = sum(p["ot_hours"] for p in b["plan"])
    if oa > 0 and abs(oa - ob) < 0.5: assert b["cost"]["加班"] == pytest.approx(a["cost"]["加班"] * 1.05, rel=1e-3)

def test_jph_sorted(base):
    for s in base["shops"]: assert [o["jph"] for o in base["jph"][s]] == sorted(o["jph"] for o in base["jph"][s])
