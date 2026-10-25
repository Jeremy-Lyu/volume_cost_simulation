"""假设登记表 A05–A10 的按天层参数（示例数据，⚠ 数值待确认）：默认关闭不改变模型；开启后方向正确"""
import copy, csv, os, pytest
import cost_functions as cf, daily
from conftest import PROTO

KEYS = ("hire_lead_months", "prev_crew", "learning_extra_lost_days", "pm_dates", "jit_swing_penalty_per_unit", "jit_free_swing_ratio", "restart_quality_cost")

@pytest.fixture(scope="module")
def cfg():
    c = daily.load_cfg(None); c.update(days=14, monthly_demand=3000, solver_time_limit=40, mip_rel_gap=5e-3); return c
@pytest.fixture(scope="module")
def r0(base, cfg): return daily.solve(base, cfg, "optimal", duals=False)

def _sig(P):
    return (sorted(P.constraints), sorted(v.name for v in P.variables()), sorted((v.name, c) for v, c in P.objective.items()),
            sorted((n, str(c)) for n, c in P.constraints.items()))

def test_defaults_are_off(cfg):
    for k in KEYS: assert k in cfg
    assert not cfg["hire_lead_months"] and cfg["prev_crew"] is None and not cfg["learning_extra_lost_days"]
    assert cfg["pm_dates"] == [] and not cfg["jit_swing_penalty_per_unit"] and not cfg["restart_quality_cost"]

@pytest.mark.parametrize("strategy", ["optimal", "weekdays", "continuous", "two_shift"])
def test_defaults_build_identical_model(base, cfg, strategy):   # 默认值 = 与没有这些键时同一个 MIP（逐条约束、逐个系数）
    plain = {k: v for k, v in cfg.items() if k not in KEYS}
    assert _sig(daily.build(base, cfg, strategy)[0]) == _sig(daily.build(base, plain, strategy)[0])

def test_a07_mix_eff_default_and_scaling(base):
    assert all(o["mix_eff"] == 1.0 for s in base["jph"] for o in base["jph"][s])
    d = copy.deepcopy(base); o = d["jph"]["PNT"][0]; a = cf.cap_per_day(d, "PNT", o, 2, 10)
    o["mix_eff"] = 0.95; assert cf.cap_per_day(d, "PNT", o, 2, 10) == pytest.approx(0.95 * a)
    assert cf.capacity(d, "PNT", o, 2, 10) == pytest.approx(0.95 * cf.capacity(base, "PNT", base["jph"]["PNT"][0], 2, 10))
def test_a07_lower_eff_not_cheaper(base, cfg, r0):
    d = copy.deepcopy(base)
    for s in d["jph"]:
        for o in d["jph"][s]: o["mix_eff"] = 0.95
    r = daily.solve(d, cfg, "optimal", duals=False); assert r["obj"] >= r0["obj"] * (1 - 5e-3)

def test_a08_pm_parse(cfg):
    assert daily.pm_days(dict(cfg, pm_dates=["10-03", "2026-10-05", 7, "11-02", "10-20"])) == {2, 4, 6}   # 14 天内、本月
def test_a08_pm_day_closed(base, cfg):
    c = dict(cfg, pm_dates=["10-03"])   # 第 3 天 = 周三（first_weekday=0）
    for strat in ("optimal", "weekdays"):
        r = daily.solve(base, c, strat, duals=False)
        assert r["kpi"]["状态"] == "Optimal" and r["kpi"]["PM停线天"] == 1
        row = r["sched"][2]; assert "JPH" not in row["BIW_状态"] and "JPH" not in row["PNT_状态"] and row["总装需求"] == 0
        assert r["kpi"]["缺货台"] == 0

def test_a10_restart_cost(base, cfg, r0):
    r = daily.solve(base, dict(cfg, restart_quality_cost=30000), "optimal", duals=False)
    n = r["cost"]["复产质量"] / 30000; assert n >= 1 - 1e-6 and abs(n - round(n)) < 1e-6   # 整数次 × 3 万
    assert r["obj"] >= r0["obj"] * (1 - 5e-3)
def test_a10_counts_restarts(base, cfg):
    r = daily.solve(base, dict(cfg, restart_quality_cost=30000), "weekdays", duals=False)
    opens = {s: ["JPH" in x[f"{s}_状态"] for x in r["sched"]] for s in ("BIW", "PNT")}
    exp = sum(1 for s in opens for j in range(1, len(opens[s])) if opens[s][j] and not opens[s][j - 1])
    assert r["cost"]["复产质量"] == pytest.approx(exp * 30000)

def test_a09_jit_penalty(base, cfg, r0):
    r = daily.solve(base, dict(cfg, jit_swing_penalty_per_unit=100, jit_free_swing_ratio=0.1), "optimal", duals=False)
    assert r["cost"].get("JIT波动", 0) >= 0 and r["obj"] >= r0["obj"] * (1 - 5e-3)
def test_a09_high_penalty_smooths(base, cfg):
    c = dict(cfg, jit_swing_penalty_per_unit=1e5, jit_free_swing_ratio=0.1)
    r = daily.solve(base, c, "optimal", duals=False)
    wd = [x["BIW_产量"] for x in r["sched"] if not x["周末"]]; free = 0.1 * 3000 / len(wd)
    assert max(abs(a - b) for a, b in zip(wd, wd[1:])) <= free + 2   # 取整误差

def test_a06_extra_lost_days(base, cfg):
    c = dict(cfg, prev_jph_tier={"BIW": 99, "PNT": 99})   # 上月档不存在 → 必换档（同 test_v52）
    a = daily.solve(base, c, "optimal", duals=False); b = daily.solve(base, dict(c, learning_extra_lost_days=1), "optimal", duals=False)
    assert b["obj"] >= a["obj"] * (1 - 5e-3)
    P, v = daily.build(base, dict(c, learning_extra_lost_days=1), "optimal"); P0, _ = daily.build(base, c, "optimal")
    cw = lambda C: {v.name: c for v, c in C.items() if v.name.startswith("crew")}   # 损失产出 = 定员班次变量 × 系数（移到左边为正）
    c1, c0 = cw(P.constraints["swlost_BIW"]), cw(P0.constraints["swlost_BIW"]); assert c0 and set(c1) == set(c0)
    assert all(c1[n] > c0[n] > 0 for n in c0)   # 每个定员班次的损失产出都更多

def test_a05_hire_lead(base, cfg, r0):
    c = dict(cfg, hire_lead_months=1, prev_crew={"BIW": [24, 1], "PNT": [24, 1]})
    P, v = daily.build(base, c, "optimal"); assert "hirelead_BIW" in P.constraints and "hirelead_PNT" in P.constraints
    r = daily.solve(base, c, "optimal", duals=False); assert r["obj"] >= r0["obj"] * (1 - 5e-3)
    for s, lab in (("BIW", "焊装定员班次"), ("PNT", "涂装定员班次")):
        assert r["kpi"][lab] in ("JPH24×1班定员", "-")   # 只能用不超过上月人数的档（这里最小档）
    assert "hirelead_BIW" not in daily.build(base, dict(cfg, prev_crew={"BIW": [24, 1]}), "optimal")[0].constraints   # 提前期 0 = 不限制

def test_register_a05_a10_status():
    rows = {r["编号"]: r for r in csv.DictReader(open(os.path.join(PROTO, "data", "假设登记表.csv"), encoding="utf-8-sig"))}
    for k in ("A05", "A06", "A07", "A08", "A09", "A10"): assert "已建参数，默认关闭，数值待确认" in rows[k]["状态"]
