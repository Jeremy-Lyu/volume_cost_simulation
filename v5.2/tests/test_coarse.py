"""六个粗参数默认不进模型。场景打开后才出现约束。不求解。"""
import copy
import data_loader as dl
import model_builder as mb
import strategies
import workbench.api as api
from scenarios import apply_knobs, load_library


def _names(d):
    P, _ = mb.build(d)
    return set(P.constraints)


def test_defaults_leave_the_model_unchanged(base):
    plain = copy.deepcopy(base)
    plain.pop("coarse", None)
    plain.pop("_coarse_pm", None)
    turned = copy.deepcopy(base)
    assert turned["coarse"]["head_up"] is None
    assert turned["coarse"]["post_switch_eff"] == 1
    assert turned["coarse"]["pm_days"] == 0
    assert turned["coarse"]["moq_fee"] == 0
    assert turned["coarse"]["restart_cost"] == 0
    assert _names(plain) == _names(turned)


def test_scenario_adds_the_six_effects(base):
    lib = {r["name"]: r for r in load_library()}
    for name in ("开停校正", "需求降且加人慢", "需求降且停工发全薪"):
        assert api.validate(lib[name]["knobs"]) == []
    d = apply_knobs(base, lib["开停校正"]["knobs"])
    names = _names(d)
    assert any(n.startswith("hup_") for n in names)
    assert any(n.startswith("hdn_") for n in names)
    assert any(n.startswith("jle_") for n in names)
    assert any(n.startswith("rstc_") for n in names)
    assert any(n.startswith("moq_on_") for n in names)
    assert d["down"][( "BIW", 2)] == 2


def test_joint_factors_are_stable_and_inside_the_bands():
    a, b = strategies.joint_factors(), strategies.joint_factors()
    assert a == b and len(a) == 20
    for row in a:
        assert 0.9 <= row["demand_all"] <= 1.1
        assert 0.9 <= row["elec"] <= 1.1
        assert 0.97 <= row["wage"] <= 1.03
        assert 0.9 <= row["avail"] <= 1.0


def test_card_marks_borrow_unverified():
    base = dict(状态="Optimal", 运营成本_万元=100, 单车_元=10, 产量=1000, 延期台月=0, 流失台=0,
                加班_万元=1, 能源_万元=2, 班次=["总装：全年 36 JPH × 2 班"], 哈希="abc", 缓存=False)
    cur = dict(base, 运营成本_万元=110, 哈希="def")
    card = dict(种类="场景", 问题="借调", 名称="自定义", 配置版本="TZ-示例", 代码版本="abc",
                运行时间="2026-10-22 00:00", 结果哈希="def", 旋钮={}, 基准=base, 本次=cur,
                科目差=[], 为什么=["产量没变"], 风险="本次未做样本风险", 待确认=[], 拍板=[],
                未验证=["借调净额 -892 万元，未验证。"], 示例数据=True)
    text = api.render_card(card)
    assert "未验证" in text
    assert "110" in text
