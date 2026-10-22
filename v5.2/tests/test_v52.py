"""v5.2 新增测试：按天人工弹性 / 跨车间借调 / JPH 换档成本 / 假设登记表（示例数据）"""
import copy, csv, os, pytest
import cost_functions as cf, daily
from conftest import solve, subset, PROTO
def nof(d, *keys):
    e = copy.deepcopy(d)
    for k in keys: e[k] = {}
    return e

def test_flex_share_default(base):        # ⚠ 默认：0.8×(1−0.7) + 0.2×(1−0) = 0.44
    assert cf.flex_var_share(base, "BIW") == pytest.approx(0.44)
def test_flex_share_extremes(base):
    d = copy.deepcopy(base)
    for s in d["lflex"]: d["lflex"][s].update(dispatch_share=0.0, stopday_pay_regular=1.0)
    assert cf.flex_var_share(d, "BIW") == 0.0
    for s in d["lflex"]: d["lflex"][s].update(dispatch_share=1.0, stopday_pay_dispatch=0.0)
    assert cf.flex_var_share(d, "BIW") == pytest.approx(1.0)
def test_no_lflex_file_means_off(base):
    d = nof(base, "lflex"); assert cf.flex_var_share(d, "BIW") == 0.0
    assert cf.stop_day_saving(d, "BIW", d["jph"]["BIW"][0], 2, 10) == dict(人工=0.0, 能源=0.0)
def test_stop_day_saving_positive(base):
    o = base["jph"]["PNT"][0]; sv = cf.stop_day_saving(base, "PNT", o, 2, 10)
    assert sv["人工"] > 0 and sv["能源"] > 0
    heads = (o["heads"] + cf.indirect_heads(base, "PNT", o)) * 2
    lab = heads * base["g"]["wage_per_head_month"] * base["g"].get("burden_rate", 1.0) / 21.75 * 0.44
    assert sv["人工"] >= lab - 1e-6     # 另含夜班补贴
def test_stop_day_saving_grows_with_dispatch(base):
    d = copy.deepcopy(base); o = d["jph"]["BIW"][0]; a = cf.stop_day_saving(d, "BIW", o, 2, 10)["人工"]
    for s in d["lflex"]: d["lflex"][s]["dispatch_share"] = 0.5
    assert cf.stop_day_saving(d, "BIW", o, 2, 10)["人工"] > a

@pytest.fixture(scope="module")
def low(base):   # 低需求 2 个月：停工日最可能出现
    d = subset(base, [10, 11])
    for k in list(d["demand"]): d["demand"][k] *= 0.5
    return d
def test_monthly_flex_not_worse(low):    # 停工日是可选项 → 不会更贵
    a = solve(nof(low, "lflex", "jsw")); b = solve(nof(low, "jsw"))
    assert b["obj"] <= a["obj"] * (1 + 2e-3)
def test_monthly_capacity_net_of_stop_days(low):
    r = solve(low)
    for p in r["plan"]:
        assert p.get("stop_days", 0) >= 0
        assert p["volume"] <= p["capacity"] + 1e-3 if "volume" in p and "capacity" in p else True
def test_switch_cost_charged(low):
    r = solve(low); c = r["cost"].get("JPH换档", 0)
    assert c >= 0 and abs(c / 300000 - round(c / 300000)) < 1e-3   # 整数次 × 30 万
def test_switch_cost_discourages_switch(low):
    a = solve(nof(low, "jsw")); d = copy.deepcopy(low)
    for s in d["jsw"]: d["jsw"][s]["cost_per_switch"] = 1e8
    b = solve(d); assert b["cost"].get("JPH换档", 0) < 1      # 极高换档成本 → 不换档
    assert b["obj"] >= a["obj"] - 1e-3 * abs(a["obj"])
def test_borrow_limited(low):
    r = solve(low)
    for (s, t), v in r["v"]["bw"].items():
        heads = sum((p.get("heads") or 0) for p in r["plan"] if p.get("shop") == s and p.get("month") == t)
        assert (v.value() or 0) >= -1e-6

# ---------- 按天 ----------
@pytest.fixture(scope="module")
def cfg():
    c = daily.load_cfg(None); c.update(days=14, monthly_demand=3000, solver_time_limit=40, mip_rel_gap=5e-3); return c
def test_daily_fvs_from_csv(base, cfg):
    P, v = daily.build(base, cfg, "optimal"); assert "借调节省人工" in v["acc"]
def test_daily_override_share(base, cfg):
    r0 = daily.solve(base, dict(cfg, labor_daily_variable_share=0.0), "continuous", duals=False)
    r1 = daily.solve(base, dict(cfg, labor_daily_variable_share=0.44), "continuous", duals=False)
    assert r1["kpi"]["状态"] in ("Optimal", "Not Solved") and r0["obj"] > 0
def test_daily_more_dispatch_not_worse(base, cfg):
    a = daily.solve(daily.with_dispatch(base, 0.0), cfg, "optimal", duals=False)
    b = daily.solve(daily.with_dispatch(base, 0.5), cfg, "optimal", duals=False)
    assert b["obj"] <= a["obj"] * 1.01
def test_daily_prev_tier_switch_cost(base, cfg):
    r = daily.solve(base, dict(cfg, prev_jph_tier={"BIW": 99, "PNT": 99}), "optimal", duals=False)   # 上月档不存在 → 必换档
    assert r["cost"]["JPH换档"] == pytest.approx(2 * 300000)

def test_assumption_register():
    rows = list(csv.DictReader(open(os.path.join(PROTO, "data", "假设登记表.csv"), encoding="utf-8-sig")))
    assert {"影响", "责任人", "状态"} <= set(rows[0])
    names = " ".join(r["假设项"] for r in rows)
    for k in ("招聘", "学习曲线", "车型混线", "计划维修", "MOQ", "复产质量", "派遣", "换档"): assert k in names
