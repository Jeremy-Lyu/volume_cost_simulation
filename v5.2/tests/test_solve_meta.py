"""求解精度写进记录。不依赖整年求解。"""
import os
import pulp
import pack_version
import solve_meta
import workbench.api as api


def _tiny():
    P = pulp.LpProblem("tiny", pulp.LpMinimize)
    x = pulp.LpVariable("x", lowBound=0, cat="Integer")
    P += x
    P += x >= 1.5
    solver, threads, seed = solve_meta.make_solver(5, 1e-4, 0, 1)
    P.solve(solver)
    meta = solve_meta.meta_from(P, pulp.value(P.objective), 1e-4, 5, 0.01, threads, seed)
    return pulp.value(P.objective), meta, threads, seed


def test_same_seed_same_objective_and_gap():
    a, ma, threads, seed = _tiny()
    b, mb, _, _ = _tiny()
    assert a == b == 2
    assert threads == 1 and seed == 1
    assert ma["Gap"] == 0 and mb["下界"] == 2
    assert ma["触时限"] is False


def test_card_says_how_far_the_number_can_be_trusted():
    base = dict(状态="Optimal", 运营成本_万元=100, 单车_元=10, 产量=1000, 延期台月=0, 流失台=0,
                加班_万元=1, 能源_万元=2, 班次=["总装：全年 36 JPH × 2 班"], 哈希="abc", 缓存=False)
    cur = dict(base, 运营成本_万元=110, 哈希="def")
    card = dict(种类="场景", 问题="电价", 名称="自定义", 配置版本="TZ-示例", 代码版本="abc",
                运行时间="2026-10-26 00:00", 结果哈希="def", 旋钮={}, 基准=base, 本次=cur,
                科目差=[], 为什么=["产量变了"], 风险="本次未做样本风险", 待确认=[], 拍板=[],
                口径=api.trust_line([{"口径状态": "待建"}, {"口径状态": "自设值"}, {"口径状态": "已对齐"}]),
                精度=api.precision_line(dict(Gap=0.001, 设定Gap=0.0001, 触时限=False, 种子=1, 线程=1), 1.1337e8),
                上限="少开班算出来的节省是上限。",
                翻转="这张卡没有重跑参数端点。")
    text = api.render_card(card)
    assert "能不能用" in text
    assert "可信等级：自设值" in text
    assert "1 项" in text
    assert "视为相同" in text
    assert "约 11.3 万元" in text
    assert "少开班算出来的节省是上限" in text


def test_example_source_map_bottoms_at_self_set():
    line = api.trust_line(api.load_source_map())
    assert line.startswith("可信等级：自设值")


def test_drift_flags_only_moves_past_ten_percent():
    assert api.drift_line({"elec": 1.05}) == ""
    watch = api.drift_line({"elec": 1.08})
    assert watch.startswith("观察") and "不自动改" not in watch
    text = api.drift_line({"elec": 1.15, "demand_month": {"9": 1.15}})
    assert "降级提示" in text and "9 月需求" in text
    assert "不自动改成另一套班次" in text


def test_scene_directions_match_the_library():
    import csv
    import os
    root = os.path.join(os.path.dirname(__file__), "..")
    with open(os.path.join(root, "data", "scenario_library.csv"), encoding="utf-8") as f:
        lib = list(csv.DictReader(f))
    with open(os.path.join(root, "..", "发布", "样例", "场景方向.csv"), encoding="utf-8") as f:
        shown = list(csv.DictReader(f))
    assert [r["name"] for r in lib] == [r["场景"] for r in shown]
    for src, row in zip(lib, shown):
        knobs = set(__import__("json").loads(src["knobs"]))
        assert knobs == set(row["动到的旋钮"].split(";"))


def test_psi_matches_the_three_bin_example():
    import monitor
    # 基准 0.3/0.5/0.2，当前 0.2/0.5/0.3。公式核对，不是已签认的门槛。
    assert abs(monitor.psi([0.3, 0.5, 0.2], [0.2, 0.5, 0.3]) - 0.081) < 0.001
    assert monitor.level(1.05) == ""
    assert monitor.level(1.08) == "观察"
    assert monitor.level(1.15) == "降级"


def test_card_names_the_parameter_pack():
    assert pack_version.assumption_line() == "假设开关：A05–A10 默认关闭"
    assert pack_version.data_hash() == pack_version.data_hash()
    assert len(pack_version.data_hash()) == 8
    text = api.render_card(dict(
        种类="场景", 问题="电价", 名称="自定义", 配置版本="TZ-示例", 代码版本="abc",
        参数哈希="deadbeef", 假设开关="假设开关：A05–A10 默认关闭",
        运行时间="2026-10-26 00:00", 结果哈希="def", 旋钮={},
        基准=dict(状态="Optimal", 运营成本_万元=100, 单车_元=10, 产量=1000, 延期台月=0, 流失台=0, 班次=["总装：全年 36 JPH × 2 班"]),
        本次=dict(状态="Optimal", 运营成本_万元=100, 单车_元=10, 产量=1000, 延期台月=0, 流失台=0, 班次=["总装：全年 36 JPH × 2 班"]),
        为什么=["产量没变"], 风险="本次未做样本风险", 待确认=[], 拍板=[],
    ))
    assert "参数 deadbeef" in text
    assert "A05–A10 默认关闭" in text


def test_ledger_does_not_add_different_baselines():
    import ledger
    path = os.path.join(os.path.dirname(__file__), "..", "..", "发布", "样例", "价值台账.csv")
    rows = ledger.load(path)
    assert ledger.net_sum(rows) == 0
    assert any(r["状态"] == "未验证" and r["净差_万元"] == "不计" for r in rows)
    poisoned = list(rows) + [dict(编号="X", 状态="模拟", 计入合计="是", 净差_万元="10")]
    assert ledger.net_sum(poisoned) == 10
    poisoned.append(dict(编号="Y", 状态="未验证", 计入合计="是", 净差_万元="99"))
    assert ledger.net_sum(poisoned) == 10


def test_daily_rerun_keeps_the_same_crew(base):
    import json
    import daily
    cfg = daily.load_cfg(None)
    cfg.update(days=14, monthly_demand=3000, solver_time_limit=40, mip_rel_gap=5e-3)
    a = daily.solve(base, cfg, "optimal", duals=False)
    b = daily.solve(base, cfg, "optimal", duals=False)
    locked = ("焊装定员班次", "涂装定员班次", "焊装开工天", "涂装开工天", "涂装启炉次数", "缺货台", "种子", "线程")
    for key in locked:
        assert a["kpi"][key] == b["kpi"][key]
    assert a["obj"] == b["obj"]
    path = os.path.join(os.path.dirname(__file__), "daily_small_golden.json")
    with open(path, encoding="utf-8") as f:
        gold = json.load(f)
    for key in locked:
        assert a["kpi"][key] == gold[key]
    assert abs(a["obj"] - gold["obj"]) < 1
    assert a["kpi"]["状态"] == gold["状态"]
    assert a["kpi"]["运营成本_万元"] == gold["运营成本_万元"]
    priced = daily.cost_fixed(base, cfg, a["fix"])
    assert priced["status"] == "Optimal"
    assert abs(priced["obj"] - a["obj"]) < 1
    rows = daily.schedule_rows(base, a)
    named = [dict(r, 车间="焊装" if r["车间"] == "BIW" else r["车间"]) for r in rows]
    again = daily.fix_from_schedule(base, cfg, named)
    for key, val in a["fix"].items():
        if key.startswith(("crew_", "y_", "off_")):
            assert again[key] == val
    reread = daily.cost_fixed(base, cfg, again)
    assert abs(reread["obj"] - a["obj"]) < 1


def test_replay_refuses_without_a_schedule():
    import daily
    import pytest
    with pytest.raises(ValueError, match="没有实际排法"):
        daily.cost_fixed(None, None, {})
    missing = os.path.join(os.path.dirname(__file__), "no-such-schedule.csv")
    with pytest.raises(FileNotFoundError, match="历史回放"):
        daily.load_fix(missing)
    blank = os.path.join(os.path.dirname(__file__), "..", "..", "发布", "样例", "实际排法.csv")
    with pytest.raises(ValueError, match="空的"):
        daily.load_schedule(blank)


def test_cross_scale_list_matches_the_tables():
    import csv
    rows = pack_version.cross_scale_rows()
    path = os.path.join(os.path.dirname(__file__), "..", "..", "发布", "样例", "未验证清单.csv")
    with open(path, encoding="utf-8") as f:
        shown = list(csv.DictReader(f))
    assert [r["科目"] for r in rows] == [r["科目"] for r in shown]
    assert all(r["状态"] == "未验证" for r in rows)
    assert rows[0]["月度"] == shown[0]["月度"] and rows[0]["按天"] == shown[0]["按天"]


def test_example_pack_is_runnable_without_actuals():
    import plant_check
    root = os.path.join(os.path.dirname(__file__), "..", "data")
    level = plant_check.readiness(plant_check.check(root)[1])
    assert level.startswith("L2")
    assert "不能回测" in level
