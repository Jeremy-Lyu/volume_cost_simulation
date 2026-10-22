import sys, os, copy, pytest
PROTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROTO)
import data_loader as dl, model_builder as mb, report as rp, cost_functions as cf

def subset(d, months):
    e = copy.deepcopy(d); e["months"] = list(months)
    e["demand"] = {k: v for k, v in e["demand"].items() if k[0] in months}
    e["g"]["solver_time_limit"] = 30
    return e

def solve(d, **kw):
    P, v = mb.build(d, **kw); st, obj = mb.solve(P, d)
    plan, cost, out, sh = rp.extract(d, v)
    return dict(P=P, v=v, st=st, obj=obj, plan=plan, cost=cost, out=out, sh=sh)

@pytest.fixture(scope="session")
def base(): return dl.load(os.path.join(PROTO, "data"))
@pytest.fixture(scope="session")
def full(): return dl.load(os.path.join(PROTO, "plants", "FULL_COST"))
@pytest.fixture(scope="session")
def base_q4(base): return solve(subset(base, [9, 10, 11]))
@pytest.fixture(scope="session")
def full_q4(full): return solve(subset(full, [9, 10, 11]))
