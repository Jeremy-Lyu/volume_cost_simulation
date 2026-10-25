"""v5.2 敏感性：定员班次按月已定（2 班定员）时，派遣比 × 白车身库容 → 停几天值不值、库容何时卡住（示例数据，⚠）
nohup python3 daily_flex_sweep.py > output/logs/flex_sweep.log 2>&1 &"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import os, sys, multiprocessing as mp
import data_loader as dl, daily as dy
SH = (0.0, 0.2, 0.5); BUF = (600, 300, 250); Q = 6000
def one(a):
    sh, buf, strat = a[:3]; ex = a[3] if len(a) > 3 else {}; d = dy.with_dispatch(dl.load(None), sh)
    c = dict(dy.load_cfg(None), monthly_demand=Q, fix_crew={"BIW": 2, "PNT": 2}, biw_buffer_max=buf, biw_buffer_start=min(200, buf // 2), **ex)
    r = dy.solve_cached(d, c, strat, None, strat == "optimal"); k = r["kpi"]
    return dict(派遣比=f"{int(sh*100)}%", 白车身库容=buf, 策略=k["策略"], 运营成本_万元=k["运营成本_万元"], 人工_万元=k["人工_万元"], 能源_万元=k["能源_万元"],
                库存_万元=k["库存_万元"], 焊装开工天=k["焊装开工天"], 涂装开工天=k["涂装开工天"], 涂装启炉次数=k["涂装启炉次数"], 最高白车身缓存=k["最高白车身缓存"],
                借调_人=k["借调_人"], 口径="整班开/整天停" if ex else "每天可少开班", 库容影子价格_元每台月=k["库容影子价格_元每台月"], 状态=k["状态"])
if __name__ == "__main__":
    X = {"same_shift_as_crew": True}
    jobs = [(s, b, "optimal") for s in SH for b in BUF] + [(s, 600, "weekdays") for s in SH] \
         + [(s, b, "optimal", X) for s in SH for b in (600, 250)] + [(s, 600, "weekdays", X) for s in SH]
    with mp.get_context("spawn").Pool(3) as p: rows = p.map(one, jobs)
    ref = {(r["派遣比"], r["口径"]): r["运营成本_万元"] for r in rows if r["策略"].startswith("每个工作日")}
    for r in rows: r["比每工作日都开省_万元"] = round(ref[(r["派遣比"], r["口径"])] - r["运营成本_万元"], 1)
    dy.wcsv(os.path.join(dy.OUT, "daily_flex_sweep.csv"), rows)
    for r in rows: print(r)
