"""v5.1 新增测试：分时电价 / 能源分项 / 启停炉 / 按天缓存（示例数据）"""
import copy, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
import data_loader as dl, cost_functions as cf, energy as E, daily, outputs_v5 as ov
from scenarios import apply_knobs
def opt(d, s, jph): return next(o for o in d["jph"][s] if o["jph"] == jph)

# ---------- 分时电价 ----------
@pytest.mark.parametrize("ver", ["2026", "2024"])
def test_tou_hours_cover_24(base, ver):
    for m in range(1, 13):
        hs = base["tou"]["hours"][(ver, m)]; assert len(hs) == 24 and None not in hs, f"{ver}-{m} 时段未覆盖 24 小时"
def test_shift_price_hand_2026(base):        # 2026 春秋 110kV：早 8–16 = 5 平 + 3 谷；中 = 7 峰 + 1 平；夜 = 7 谷 + 1 平
    assert cf.price(base, 10, 1) == pytest.approx((5*0.5813 + 3*0.2961) / 8)
    assert E.shift_price(base, 10, 2) == pytest.approx(((5*0.5813 + 3*0.2961) + (7*0.9854 + 0.5813)) / 16)
    assert E.shift_price(base, 10, 3) == pytest.approx(((5*0.5813 + 3*0.2961) + (7*0.9854 + 0.5813) + (7*0.2961 + 0.5813)) / 24)
def test_mid_shift_most_expensive_2026(base):   # 新政：中班最贵、夜班最便宜
    p = E.hour_prices(base, 10); mid = sum(p[16:24]) / 8; day = sum(p[8:16]) / 8; night = sum(p[0:8]) / 8
    assert mid > day > night
def test_tou_version_2024_backtest(base):    # 2024 春秋 早班：8–11、13–16 峰（6h）+ 11–13 谷（2h）
    d = apply_knobs(base, {"tou_version": "2024"})
    assert cf.price(d, 10, 1) == pytest.approx((6*0.9398 + 2*0.2212) / 8)
    assert cf.price(d, 10, 1) > cf.price(base, 10, 1)    # 旧政白天高峰 → 早班更贵
def test_voltage_knob(base):
    assert cf.price(apply_knobs(base, {"voltage": "10kV"}), 10, 1) > cf.price(base, 10, 1)
def test_elec_scenario_scales_tou(base):
    assert cf.price(dl.scenario(base, elec=1.2), 10, 2) == pytest.approx(1.2 * cf.price(base, 10, 2))
def test_tou_off_backcompat(base):           # 关闭分时 = v5 单一电价
    d = copy.deepcopy(base); d["tou"] = None
    assert cf.price(d, 10) == pytest.approx(0.75) and "能源固定" in cf.fixed_breakdown(d, "PNT", opt(d, "PNT", 30), 2, 10)
def test_ot_priced_in_own_period(base):      # 加班（休息日 8–16）按早班时段价，不按中班
    assert cf.ot_price(base, 10) == pytest.approx(cf.price(base, 10, 1)) and cf.ot_price(base, 10) < cf.price(base, 10, 2)

# ---------- 能源分项 / 启停炉 ----------
def test_startup_below_8000(base):           # 电泳周末不停热 → 启炉只含烘房+喷房，应低于原 8,000 元暂定值
    c = E.startup_cost(base, "PNT", 10); assert 3000 < c < 8000
    assert c == pytest.approx(4500 * E.heatup_price(base, 10, 2) + 900 * 3.6)
def test_breakeven_hand(base):               # 临界间隔 = 启炉费 ÷ (保温费/h − 停炉费/h)
    o = opt(base, "PNT", 30); p = E.day_price(base, 10)
    hold = 0.30*3900*p + 450*0.40*3.6; off = (0.05*3900 + 150)*p + 40*3.6
    assert E.breakeven_hours(base, "PNT", 3900, 10) == pytest.approx(E.startup_cost(base, "PNT", 10) / (hold - off))
    assert 2 < E.breakeven_hours(base, "PNT", 3900, 10) < 24
def test_weekend_auto_shutdown_paint(base):  # 周末 48h ≫ 临界间隔 → auto 选停炉
    assert cf.energy_policy(base, "PNT", opt(base, "PNT", 30), 2, 10)["周末"] == "停炉"
def test_weekend_hold_costs_more(base):
    o = opt(base, "PNT", 30); a = sum(cf.energy_parts(base, "PNT", o, 2, 10).values())
    b = sum(cf.energy_parts(apply_knobs(base, {"weekend_policy": {"PNT": "hold"}}), "PNT", o, 2, 10).values())
    assert b > a
def test_energy_parts_sum(base):             # 固定能源 = 各分项之和；含需量电费 = 0.85 × kW × 40.8
    o = opt(base, "PNT", 36); p = cf.energy_parts(base, "PNT", o, 2, 10)
    assert cf.energy_fixed(base, "PNT", o, 2, 10) == pytest.approx(sum(p.values()))
    assert p["需量电费"] == pytest.approx(0.85 * 4300 * 40.8)
    assert set(p) >= {"能源-电(运行)", "能源-电(待机)", "能源-天然气", "启停能耗", "需量电费"}
def test_gas_per_unit_decreases_with_jph(base):   # 烘房按小时耗气：同产量下 JPH 越高，单车用气越少
    g30 = E.estimate_per_unit(base, "PNT", opt(base, "PNT", 30), 2, 10, 9000)["能源-天然气"]
    g36 = E.estimate_per_unit(base, "PNT", opt(base, "PNT", 36), 2, 10, 9000)["能源-天然气"]
    assert g36 < g30
def test_gas_scenario(base):
    o = opt(base, "PNT", 30)
    assert cf.energy_parts(apply_knobs(base, {"gas": 1.1}), "PNT", o, 2, 10)["能源-天然气"] == pytest.approx(1.1 * cf.energy_parts(base, "PNT", o, 2, 10)["能源-天然气"])

# ---------- 按天排产 ----------
@pytest.fixture(scope="module")
def dsmall(base):
    c = daily.load_cfg(); c.update(days=14, monthly_demand=4500, solver_time_limit=60, mip_rel_gap=2e-3); return base, c
@pytest.fixture(scope="module")
def dopt(dsmall): b, c = dsmall; return daily.solve(b, c, "optimal", duals=True)
def test_daily_buffer_balance_and_bounds(dsmall, dopt):
    b, c = dsmall; prev = c["biw_buffer_start"]
    for r in dopt["sched"]:
        assert prev + r["BIW_产量"] - r["PNT_产量"] == pytest.approx(r["白车身缓存"], abs=2)
        assert c["biw_buffer_min"] - 1 <= r["白车身缓存"] <= c["biw_buffer_max"] + 1; prev = r["白车身缓存"]
    assert dopt["sched"][-1]["白车身缓存"] >= c["biw_buffer_start"] - 1 and dopt["kpi"]["缺货台"] == 0
def test_daily_startup_after_shutdown(dsmall, dopt):   # 每次 停炉→开工 都计一次启炉
    sch = dopt["sched"]
    n = sum(1 for a, b_ in zip(sch, sch[1:]) if a["PNT_状态"] == "停炉" and b_["PNT_状态"] != "停炉")
    assert dopt["kpi"]["涂装启炉次数"] == n
def test_daily_continuous_no_startup(dsmall):
    b, c = dsmall; r = daily.solve(b, c, "continuous", duals=False)
    assert r["kpi"]["涂装启炉次数"] == 0 and all(("3班" in x["PNT_状态"]) for x in r["sched"] if not x["周末"])
def test_daily_sync_same_days(dsmall):
    b, c = dsmall; r = daily.solve(b, c, "sync", duals=False)
    assert all(("JPH" in x["BIW_状态"]) == ("JPH" in x["PNT_状态"]) for x in r["sched"])
def test_daily_optimal_not_worse(dsmall, dopt):   # 自主排产 ≤ 任何受限策略（gap 内）
    b, c = dsmall
    for s in ("continuous", "sync", "two_shift"):
        assert dopt["obj"] <= daily.solve(b, c, s, duals=False)["obj"] * (1 + 3e-3)
def test_daily_tight_buffer_costs_more(dsmall, dopt):   # 库容收紧不会更省；影子价格 ≥ 0
    b, c = dsmall; r = daily.solve(b, c, "optimal", buf_max=220, duals=False)
    assert r["obj"] >= dopt["obj"] * (1 - 3e-3) and (dopt["kpi"]["库容影子价格_元每台月"] or 0) >= -1e-6

# ---------- 决策单基准一致 ----------
def test_decision_sheet_baseline_check():
    ctx = dict(方案=[dict(方案="成本优先", 运营成本_万元=100)], 瀑布基准_万元=103, 结论基准_万元=100)
    assert ov.check_baseline(ctx) and not ov.check_baseline(dict(ctx, 瀑布基准_万元=100))
