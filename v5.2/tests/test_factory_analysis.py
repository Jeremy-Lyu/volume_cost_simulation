"""工厂情景分析：旋钮落点、情景表、解读规则。不跑全年求解。"""
import factory_analysis as fa
from scenarios import apply_knobs

def test_new_knobs_land(base):
    d = apply_knobs(base, {"max_shifts": 2, "dispatch": 0.5, "penalty": 8000, "buffer": {"PNT": 0.5},
                           "ftt": {"BIW": 0.9}, "switch_cost": 1e6, "night_mul": 2, "stop_pay": 1, "borrow": 0,
                           "oee": {"PNT|6": 0.8}, "attendance": {"ALL|2": 0.88}, "ramp": {"TCF|1": 0.7},
                           "backlog_mul": 2})
    assert 3 not in d["shift"] and 2 in d["shift"] and 0 in d["shift"]
    assert d["lflex"]["BIW"]["dispatch_share"] == 0.5
    assert d["lflex"]["BIW"]["stopday_pay_regular"] == 1
    assert d["lflex"]["PNT"]["borrow_limit"] == 0
    assert d["g"]["shortage_penalty"] == 8000
    assert d["g"]["backlog_cost_per_unit_month"] == base["g"]["backlog_cost_per_unit_month"] * 2
    assert d["shop"]["PNT"]["buffer_cap"] == base["shop"]["PNT"]["buffer_cap"] * 0.5
    assert d["shop"]["BIW"]["buffer_cap"] == base["shop"]["BIW"]["buffer_cap"]
    assert d["qual"]["BIW"] == 0.9
    assert d["jsw"]["TCF"]["cost_per_switch"] == 1e6
    assert d["g"]["night_allowance_per_head_night"] == base["g"]["night_allowance_per_head_night"] * 2
    assert d["oee"][("PNT", 6)]["time_rate"] == 0.8
    assert d["att"][("STP", 2)] == 0.88 and d["att"][("TCF", 2)] == 0.88
    assert d["ramp"][("TCF", 1)] == 0.7
    c = apply_knobs(base, {"cap_mul": 1.15})
    key = next(iter(base["cap"]))
    assert c["cap"][key] == base["cap"][key] * 1.15
    assert apply_knobs(base, {"fg_hold": 800})["g"]["fg_hold_cost_per_unit_month"] == 800

def test_no_flex_clears_after_dispatch(base):
    d = apply_knobs(base, {"dispatch": 0.4, "no_flex": True, "no_switch": True})
    assert d["lflex"] == {} and d["jsw"] == {}

def test_catalog_names_unique_and_refs_exist(base):
    cases = fa.catalog(base)
    names = [c["name"] for c in cases]
    assert names[0] == "基准" and len(names) == len(set(names))
    assert {c["against"] for c in cases if c["against"]} <= set(names)
    assert any(c["qid"] == "demand" for c in cases)
    assert sum(c["场景"].startswith("涂装全年") for c in ({"场景": c["name"], **c} for c in cases)) == 4
    assert "需求×2" not in names and all(c["qid"] not in ("bundle", "stack", "hyp") for c in cases)
    full = fa.catalog(base, extreme=True)
    full_names = [c["name"] for c in full]
    assert len(full_names) == len(set(full_names))
    assert {c["against"] for c in full if c["against"]} <= set(full_names)
    assert "需求×2" in full_names and any(c["qid"] == "hyp" for c in full)
    assert len(full) > len(cases)

def test_extreme_switch_reads_table(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "switches.csv").write_text("key,value,说明\nextreme,1,打开\n", encoding="utf-8")
    monkeypatch.setattr(fa, "H", str(tmp_path))
    monkeypatch.setattr(fa.sys, "argv", ["factory_analysis.py"])
    assert fa.extreme_enabled() is True
    assert fa.extreme_enabled(False) is False
    monkeypatch.setattr(fa.sys, "argv", ["factory_analysis.py", "--no-extreme"])
    assert fa.extreme_enabled() is False

def test_response_labels_and_demand_reading():
    assert fa.response_label(dict(升档月=2, 加开班月=1, 降档月=0, 减班月=0, 加班差h=0, 停工日差=0, 流失差=0, 延期差=0, 预产="")) == "升档+加开班"
    assert fa.response_label(dict(升档月=0, 加开班月=0, 降档月=3, 减班月=0, 加班差h=-100, 停工日差=4, 流失差=0, 延期差=0, 预产="")) == "降档+少加班+停工日"
    q = "需求偏离到什么程度，排产和交付才变？"
    def row(level, lost, delay, chg, unit, how):
        return dict(状态="Optimal", 水平=level, 流失=lost, 延期台月=delay, 方案变化=chg, 单车_元=unit,
                    应对=how, 方案变化说明="涂装加开三班", 运营成本_万元=1, 较参照_万元=1)
    text = fa.read_demand([
        row(0.8, 0, 0, 4, 4200, "降档"),
        row(1.1, 0, 0, 2, 3500, "加开班"),
        row(1.4, 500, 800, 6, 3600, "延期或流失"),
    ], [])
    assert "×0.8" in text and "×1.1" in text and "×1.4" in text and "流失" in text

def test_price_reading_separates_schedule():
    def row(name, chg, delta, note=""):
        return dict(状态="Optimal", 场景=name, 方案变化=chg, 较参照_万元=delta, 方案变化说明=note, 应对="方案不变" if not chg else "加开班")
    text = fa.read_price([row("电价+30%", 0, 800), row("夜班补贴×3", 3, 120, "涂装5月36×2→36×3")], [])
    assert "不改排产" in text and "电价+30%" in text and "会改班次" in text and "夜班补贴×3" in text

def test_bundle_names_the_cheap_option_that_delivers():
    def row(name, ref, lost, cost, delta):
        return dict(状态="Optimal", 场景=name, 参照=ref, 流失=lost, 延期台月=0,
                    运营成本_万元=cost, 较参照_万元=delta, 判断="x")
    text = fa.read_bundle([
        row("只改表", "高需求", 0, 100, 10),
        row("只加快", "高需求", 500, 80, -5),
    ], [row("高需求", "基准", 800, 90, 0)])
    assert "只改表" in text and "最省钱" in text and "只加快" in text and "800" in text

def test_hyp_reading_flags_a_real_change():
    ref = dict(状态="Optimal", 场景="已改表", 参照="基准", 流失=0, 延期台月=0, 较参照_万元=0, 应对="方案不变")
    moved = dict(状态="Optimal", 场景="不能加人", 参照="已改表", 流失=400, 延期台月=800,
                 较参照_万元=220, 应对="延期或流失")
    quiet = dict(状态="Optimal", 场景="发全薪", 参照="已改表", 流失=0, 延期台月=10,
                 较参照_万元=8, 应对="方案不变")
    text = fa.read_hyp([moved, quiet], [ref, moved, quiet])
    assert "要改建议" in text and "不能加人" in text and "不改变建议" in text and "发全薪" in text

def test_money_split_keeps_penalty_out_and_adds_up():
    before = {"人工": 1000e4, "能源-电(运行)": 100e4, "OH": 500e4, "缺口惩罚(流失)": 0}
    after = {"人工": 1200e4, "能源-电(运行)": 150e4, "OH": 540e4, "缺口惩罚(流失)": 300e4}
    s = fa.money_split(before, after, 290)
    assert s["人工差_万元"] == 200 and s["能源差_万元"] == 50 and s["罚款差_万元"] == 300
    assert abs(s["人工差_万元"] + s["能源差_万元"] + s["车间差_万元"] - 290) < 0.05

def test_shift_change_is_plain_language():
    a = [dict(shop="BIW", month=1, jph=36, shifts=2), dict(shop="BIW", month=2, jph=36, shifts=2)]
    b = [dict(shop="BIW", month=1, jph=30, shifts=2), dict(shop="BIW", month=2, jph=30, shifts=2)]
    text = fa.describe_changes(a, b)
    assert "每小时 36 台" in text and "每小时 30 台" in text and "开两班" in text and "×" not in text

def test_factor_identity_sentence():
    rows = [dict(状态="Optimal", 场景=n, 较参照_万元=100, 方案变化=2, 判断="一样") for n in
            ("涂装全年开动率×0.85", "涂装全年OEE×0.85", "涂装全年FTT=0.85", "涂装全年出勤85%")]
    text = fa.read_factor(rows, [])
    assert "同一个产能折扣" in text
