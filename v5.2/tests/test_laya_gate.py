"""Laya 入口的否决规则。不加载模型。"""
import laya_gate as g

def ans(choice, conf=0.8):
    return {"choice": choice, "confidence": conf, "probabilities": {choice: conf}}

def pack(**kw):
    base = {k: ans("unclear", 0.1) for k in g.QUESTIONS}
    base.update(kw)
    return base

def row(lost, delta=0, ref="参照", labor=0, energy=0, shop=0, pen=0, delay=0):
    return dict(流失=lost, 延期台月=delay, 较参照_万元=delta, 参照=ref,
                人工差_万元=labor, 能源差_万元=energy, 车间差_万元=shop, 罚款差_万元=pen)

def rows14():
    b = g.BANDS["y14"]
    return {
        b["base"]: row(2475, ref="基准"),
        b["speed"]: row(2475, -4219.9, "需求×1.4", -3715.1, -272.3, -232.5, 0),
        b["cap"]: row(0, 138.8, "需求×1.4", 347.8, 34.3, -243.3, -7425),
        b["warehouse"]: row(0, 1349.8, "需求×1.4", 473.5, 53.6, 822.7, -7425),
        b["cap_night"]: row(0, 1122.4, "需求×1.4", 895.3, 711.4, -484.3, -7425, delay=1920),
    }

def test_speed_up_is_vetoed_when_no_extra_cars():
    raw = pack(demand=ans("y14"), cap=ans("planning"), hire=ans("lead_time"),
               night=ans("allowed"), ask=ans("speed_line"))
    out = g.verdict(raw, rows14())
    assert out["ok"] and out["action"] == "raise_cap"
    assert "否决" in out["text"] and "138.8" in out["text"] and "模型算不出" in out["text"]
    assert "罚款" in out["text"]

def test_hard_cap_uses_warehouse():
    raw = pack(demand=ans("y14"), cap=ans("hard"), hire=ans("unclear", 0.2),
               night=ans("allowed"), ask=ans("raise_cap"))
    out = g.verdict(raw, rows14())
    assert out["action"] == "warehouse"
    assert "不建议改那张表" in out["text"] and "1,349.8" in out["text"]

def test_night_ban_at_higher_volume_blocks_cap_only():
    b = g.BANDS["y16"]
    rows = {
        b["base"]: row(16800),
        b["speed"]: row(16800),
        b["cap"]: row(0, -4604.2, "需求×1.6"),
        b["warehouse"]: row(14400),
        b["cap_night"]: row(7580, -2406.1, "需求×1.6"),
    }
    raw = pack(demand=ans("y16"), cap=ans("planning"), hire=ans("this_month"),
               night=ans("banned"), ask=ans("raise_cap"))
    out = g.verdict(raw, rows)
    assert out["action"] is None
    assert "7580" in out["text"] and "不许开夜班" in out["text"]

def test_literal_phrase_overrides_a_confident_miss():
    raw = pack(demand=ans("y20", 0.9), cap=ans("planning"), hire=ans("this_month"),
               night=ans("allowed", 0.92), ask=ans("raise_cap"))
    state = "订单多六成。月度上限可以改。不许开夜班。人这个月就能招齐。想先改那张月度上限的表。"
    b = g.BANDS["y16"]
    rows = {b["base"]: row(16800), b["speed"]: row(16800), b["cap"]: row(0),
            b["warehouse"]: row(14400), b["cap_night"]: row(7580)}
    out = g.verdict(raw, rows, state)
    assert out["picks"]["demand"] == "y16" and out["picks"]["night"] == "banned"
    assert out["action"] is None and any("不许开夜班" in n for n in out["notes"])

def test_molds_can_still_be_added_stays_a_planning_cap():
    raw = pack(demand=ans("y14"), cap=ans("planning"), hire=ans("lead_time"),
               night=ans("allowed"), ask=ans("speed_line"))
    state = "订单要比今年多出四成。月度上限只是计划表，模具和码头还能加。人要两个月才能到岗。夜班可以开。我们想先把四条线都加快。"
    out = g.verdict(raw, rows14(), state)
    assert out["picks"]["cap"] == "planning" and out["action"] == "raise_cap"
    assert "否决" in out["text"] and "模型算不出" in out["text"]

def test_unknown_volume_reports_no_cars():
    raw = pack(demand=ans("unclear", 0.2))
    out = g.verdict(raw, rows14())
    assert out["ok"] is False and "不报台数" in out["text"]
