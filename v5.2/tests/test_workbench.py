"""工作台：范围、班次压缩、决策卡数字只来自传入的结果。不启动求解器。"""
import json
import workbench.api as api


def test_compress_full_year_and_single_month():
    plan = []
    for m in range(1, 13):
        plan.append(dict(shop="TCF", month=m, jph=36, shifts=2))
        plan.append(dict(shop="PNT", month=m, jph=36, shifts=3 if m in (5, 10) else 2))
    lines = api.compress_shifts(plan, ["PNT", "TCF"])
    assert lines[0] == "涂装：1–4 月 36 JPH × 2 班；5 月 36 JPH × 3 班；6–9 月 36 JPH × 2 班；10 月 36 JPH × 3 班；11–12 月 36 JPH × 2 班"
    assert lines[1] == "总装：全年 36 JPH × 2 班"


def test_validate_rejects_out_of_range():
    assert api.validate({"elec": 3})
    assert api.validate({}) == []
    assert api.validate({"elec": 1.2, "down": {"BIW|6": 5}}) == []


def test_card_uses_only_given_numbers():
    base = dict(状态="Optimal", 运营成本_万元=100, 单车_元=10, 产量=1000, 延期台月=0, 流失台=0,
                加班_万元=1, 能源_万元=2, 班次=["总装：全年 36 JPH × 2 班"], 哈希="abc", 缓存=False)
    cur = dict(base, 运营成本_万元=110, 单车_元=11, 产量=1100, 哈希="def")
    card = dict(种类="场景", 问题="电价", 名称="自定义", 配置版本="TZ-示例", 代码版本="abc",
                运行时间="2026-10-21 00:00", 结果哈希="def", 旋钮={"elec": 1.2}, 基准=base, 本次=cur,
                科目差=[{"科目": "能源-电(运行)", "差额_万元": 10}],
                为什么=["产量变了"], 风险="本次未做样本风险", 待确认=[], 拍板=[], 示例数据=True)
    text = api.render_card(card)
    assert "示例数据" in text
    assert "110" in text and "100" in text
    assert "+10" in text
    assert "本次未做样本风险" in text
    assert "99999" not in text


def test_warnings_cover_borrow_and_energy_knob():
    cost = {"借调节省人工": -1e7, "借调占用": 6e6}
    warns = api.warnings_for({"elec": 1.2}, cost, "Optimal")
    ids = [w["编号"] for w in warns]
    assert ids[0] == "A03"
    assert "未验证" in warns[0]["文字"]
    assert "A01" in ids and "A11" in ids
    assert api.unverified_lines(cost)[0].startswith("借调净额")
    assert api.unverified_lines({"借调节省人工": -3e5, "借调占用": -1e5}) == []
    assert "A11" not in [w["编号"] for w in api.warnings_for({}, cost, "Optimal")]


def test_ask_examples_do_not_invent_a_run():
    import workbench.ask as ask
    peak = ask.parse("9到12月需求涨15%，成本会涨多少？要不要加班次？")
    assert peak["status"] == "confirm" and peak["名称"] == "旺季冲量"
    assert peak["旋钮"]["demand_month"]["12"] == 1.15
    elec = ask.parse("电价涨两成多花多少？")
    assert elec["旋钮"] == {"elec": 1.2} and elec["status"] == "confirm"
    stop = ask.parse("焊装停一周会怎样？")
    assert stop["status"] == "ask" and "旋钮" not in stop
    follow = ask.parse("就用 6 月", stop)
    assert follow["旋钮"] == {"down": {"BIW|6": 5}} and follow["名称"] == "焊装停线一周"
    refuse = ask.parse("帮我估一下明年工厂的真实总成本。")
    assert refuse["status"] == "refuse" and refuse["旋钮"] == {}


def test_explain_rejects_numbers_outside_the_card():
    import workbench.ask as ask
    card = {"本次": {"运营成本_万元": 110}, "基准": {"运营成本_万元": 100}, "正文": "全年运营成本 110 万元，比基准 100 万元 +10 万元。"}
    assert ask.stray_numbers(ask.explain(card), card) == []
    assert ask.stray_numbers("成本是 99999 万元", card) == ["99999"]


def test_library_exercises_resolve():
    knobs, name, _ = api.exercise_knobs(api.EXERCISES[0])
    assert name == "旺季冲量"
    assert knobs["demand_month"]["9"] == 1.15
    knobs, _, _ = api.exercise_knobs(api.EXERCISES[1])
    assert knobs == {"elec": 1.2}
    assert json.dumps(knobs)
