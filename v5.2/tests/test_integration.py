"""L2 守恒/平衡 + L3 口径一致：求解后检查（9–11 月子样本，示例数据）"""
import pytest, cost_functions as cf
from conftest import solve, subset
TOL = 1.0  # 元

def _check_balance(d, r):
    v = r["v"]; S, M, T = d["shops"], d["models"], d["months"]
    for a, b in zip(S[:-1], S[1:]):
        for m in M:
            for t in T:
                prev = v["inv"][(a,m,t-1)].value() if t > T[0] else 0
                assert prev + v["x"][(a,m,t)].value() == pytest.approx(v["x"][(b,m,t)].value() + v["inv"][(a,m,t)].value(), abs=1e-3)

def test_status_optimal(base_q4): assert base_q4["st"] == "Optimal"
def test_one_option_per_shop_month(base, base_q4):
    d = subset(base, [9,10,11])
    for s in d["shops"]:
        for t in d["months"]:
            assert sum(round(var.value()) for (ss,i,k,tt), var in base_q4["v"]["y"].items() if ss==s and tt==t) == 1
def test_flow_balance(base, base_q4): _check_balance(subset(base,[9,10,11]), base_q4)
def test_volume_le_capacity(base_q4):
    for r in base_q4["plan"]: assert r["volume"] <= r["capacity"] + 1
def test_ot_le_hard_cap(base, base_q4):   # v4：人均加班 ≤ 绝对上限；超 36h 部分单列
    for r in base_q4["plan"]:
        assert r["ot_per_head"] <= base["g"]["ot_hard_cap_per_head_month"] + 0.1
        assert r["ot_hours"] - r["ot_excess_hours"] <= base["shop"][r["shop"]]["ot_max_hours_month"] * max(r["shifts"],1) + 0.1
def test_selfcheck_base(base, base_q4):
    import report as rp; assert rp.selfcheck(subset(base,[9,10,11]), base_q4["v"], base_q4["obj"]) == []
def test_selfcheck_full(full, full_q4):
    import report as rp; assert rp.selfcheck(subset(full,[9,10,11]), full_q4["v"], full_q4["obj"]) == []
def test_demand_met(base, base_q4):
    d = subset(base,[9,10,11]); assert base_q4["out"] + base_q4["sh"] >= sum(d["demand"].values()) - 1

def test_cost_parts_sum_to_objective_base(base_q4):
    assert sum(base_q4["cost"].values()) == pytest.approx(base_q4["obj"], abs=TOL)

def test_cost_parts_sum_to_objective_fullcost(full, full_q4):
    """全成本口径：报表分项(去掉物料；−边际贡献已是科目) 应等于 目标值"""
    rep = sum(x for k, x in full_q4["cost"].items() if k != "物料")
    assert rep == pytest.approx(full_q4["obj"], rel=1e-6), f"报表−目标 = {(rep-full_q4['obj'])/1e4:.0f} 万元"

def test_buffer_cap_is_total_not_per_model(base):
    """缓存上限应约束车间总在制（物理库位），而不是每个车型各一份"""
    import copy
    d = subset(base,[9,10,11]); d = copy.deepcopy(d)
    for s in d["shops"]: d["shop"][s]["buffer_cap"] = 100 if s != d["shops"][-1] else 0
    for s in d["shops"]: d["shop"][s]["hold_cost_per_unit_month"] = -1e-3 if s!=d["shops"][-1] else 0  # 诱导模型尽量多存
    r = solve(d); v = r["v"]
    worst = max(sum(v["inv"][(s,m,t)].value() for m in d["models"]) for s in d["shops"][:-1] for t in d["months"])
    assert worst <= 100 + 1e-6, f"单车间总缓存达 {worst:.0f}（上限100，按车型各算一份）"
