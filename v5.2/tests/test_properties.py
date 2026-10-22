"""L4 单调性/敏感性、L5 边界极端、L6 与穷举基准对照"""
import copy, itertools, pytest, cost_functions as cf
from conftest import solve, subset

@pytest.fixture(scope="module")
def d1(base): return subset(base, [10])

def scaled(d, dem=1.0, wage=1.0, elec=1.0):
    e = copy.deepcopy(d); e["demand"] = {k: v*dem for k, v in e["demand"].items()}
    e["g"]["wage_per_head_month"] *= wage; e["g"]["elec_price"] *= elec; return e

@pytest.mark.parametrize("kw", [dict(dem=1.05), dict(wage=1.05), dict(elec=1.2)])
def test_monotone_cost(d1, kw):
    b = solve(d1)["obj"]; u = solve(scaled(d1, **kw))["obj"]
    assert u >= b - 1, f"{kw}: 成本下降 {b-u:.0f}"

def test_zero_demand(d1):
    r = solve(scaled(d1, dem=0.0)); assert r["out"] == pytest.approx(0, abs=1e-6) and r["sh"] == pytest.approx(0, abs=1e-6)
    # v4 规则3：零需求时各车间选 0 班（整月停线），只付停线固定成本
    assert all(p["shifts"] == 0 for p in r["plan"]) and "人工" not in {k for k, x in r["cost"].items() if x > 1}

def test_extreme_demand_shortage(d1):
    r = solve(scaled(d1, dem=3.0))
    assert r["sh"] > 0 and r["st"] == "Optimal"

def test_bruteforce_matches_solver(d1):
    """穷举：单月(10月)四车间各 3档×3班 = 6561 组合，固定 y 后用 LP 求加班/缓存，取最小，应与 MIP 一致。
    为加速，只穷举总装、其余车间固定为 MIP 解。"""
    r = solve(d1); v = r["v"]; best = None
    fixed = {k: round(x.value()) for k, x in v["y"].items()}
    S = d1["shops"]; last = S[-1]
    for i, k in itertools.product(range(len(d1["jph"][last])), d1["shift"]):
        fy = {kk: (vv if kk[0] != last else int(kk[1]==i and kk[2]==k)) for kk, vv in fixed.items()}
        rr = solve(d1, fix_y=fy)
        if rr["st"] == "Optimal" and (best is None or rr["obj"] < best): best = rr["obj"]
    assert r["obj"] <= best + 1, f"MIP {r['obj']:.0f} > 穷举 {best:.0f}"

def test_repeatable(d1):
    a = solve(d1)["obj"]; b = solve(d1)["obj"]; assert a == pytest.approx(b, abs=1)
