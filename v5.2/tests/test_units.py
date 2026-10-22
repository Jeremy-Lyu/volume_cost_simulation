"""L1 单元测试：手算样例（示例数据，对应 项目分析总结.md 7.4 总装10月）"""
import pytest, cost_functions as cf
def opt(d, s, jph): return next(o for o in d["jph"][s] if o["jph"] == jph)

def test_hours_tcf_oct(base):            # 7.5h × 2班 × 18天 = 270h
    assert cf.hours(base, 2, 10, "TCF") == pytest.approx(270)
def test_capacity_tcf_36x2(base):        # 36 × 270 = 9720 台
    assert cf.capacity(base, "TCF", opt(base,"TCF",36), 2, 10) == pytest.approx(9720)
def test_ot_units(base):                 # (11000−9720)/36 = 35.56h
    assert cf.ot_units(base, "TCF", opt(base,"TCF",36), 10, 35.5556) == pytest.approx(1280, abs=0.1)
def test_labor_1shift(base):              # 1班无夜班：425×9000
    assert cf.labor(base, "TCF", opt(base,"TCF",36), 1, 10) == pytest.approx(425*9000)
def test_labor_3shift_night(base):       # v4：3班 360×3×9000 + 360人×1夜班×18天×30元
    assert cf.labor(base, "TCF", opt(base,"TCF",30), 3, 10) == pytest.approx(360*3*9000 + 360*18*30)
def test_labor_2shift_night(base):       # v4 规则6：两班倒也有夜班补贴 425×18×30
    assert cf.labor(base, "TCF", opt(base,"TCF",36), 2, 10) == pytest.approx(425*2*9000 + 425*18*30)
def test_zero_shift_costs(base):         # v4 规则3：0 班只有停线固定成本
    fb = cf.fixed_breakdown(base, "TCF", opt(base,"TCF",24), 0, 10)
    assert fb == {"停线固定": base["shop"]["TCF"]["idle_fixed_month"]} and cf.capacity(base, "TCF", opt(base,"TCF",24), 0, 10) == 0
def test_ot_cost_per_hour(base):         # v4 规则5：425 × (9000/174×1.5) + 1000kW×0.75（v5 单一电价口径：关闭分时）
    import copy; d = copy.deepcopy(base); d["tou"] = None
    assert cf.ot_cost_per_hour(d, "TCF", opt(d,"TCF",36), 10) == pytest.approx(425*9000/174*1.5 + 1000*0.75)
def test_ot_cost_per_hour_tou(base):     # v5.1：加班放在休息日 8–16 点，2026 春秋 110kV：(5×0.5813+3×0.2961)/8 = 0.47434
    assert cf.ot_cost_per_hour(base, "TCF", opt(base,"TCF",36), 10) == pytest.approx(425*9000/174*1.5 + 1000*(5*0.5813+3*0.2961)/8)
def test_down_days_reduce_hours(base):
    import copy; d = copy.deepcopy(base); d["down"] = {("BIW", 6): 5}
    assert cf.hours(d, 2, 6, "BIW") == pytest.approx(7.5*2*(base["days"][6]-5))

def test_fixed_breakdown_no_double_count(full):
    """固定成本分项之和 应等于 人工合计(直接+间接+福利+夜班)+能源固定+班车+外包+换型"""
    o = opt(full, "TCF", 36); k, t = 2, 10
    fb = cf.fixed_breakdown(full, "TCF", o, k, t)
    expect = cf.labor(full, "TCF", o, k, t) + cf.energy_fixed(full, "TCF", o, k, t) \
           + cf.bus(full, "TCF", o, k, t) + cf.outsourcing(full, "TCF", o, k, t) + cf.changeover_cost(full, "TCF")
    assert sum(fb.values()) == pytest.approx(expect), f"差额={sum(fb.values())-expect:.0f}（间接人工被计两次）"

def test_per_unit_accrual_counted_once(full):
    """保修/碳 是单车(整车)计提，var_cost_per_unit 不应在每个车间都加一次"""
    per_shop = [cf.var_cost_per_unit(full, s, 10) - full["shop"][s]["kwh_per_unit"]*cf.price(full,10)
                - full["shop"][s]["oh_var_per_unit"] - cf.quality_cost_per_unit(full, s) for s in full["shops"]]
    assert sum(per_shop) == pytest.approx(cf.other_per_unit(full)), f"目标中计了 {sum(per_shop)/cf.other_per_unit(full):.0f} 次"

def test_scenario_wage_moves_ot_rate(base):
    """工资+5% 场景：加班单价是否同步？（设计核对项）"""
    import data_loader as dl
    e = dl.scenario(base, wage=1.05)
    assert cf.ot_rate(e) == pytest.approx(cf.ot_rate(base)*1.05)
