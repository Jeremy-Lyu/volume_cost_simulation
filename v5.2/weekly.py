"""周计划层（P2，周/日层第一版）：排序规则(Car Sequencing) + 换色批量 + 技能矩阵
从月度方案派生周度车型产量，产出两种排产方案并量化权衡：
  方案A 序列优先：严格满足滑动窗口高工时间隔，颜色切换多
  方案B 颜色优先：按颜色成批（每色≥最小批量），颜色切换少，高工时间隔可能超限
输入（可选，均有缺省）：models.csv(model,config_load,color)、color_batch.csv(color,batch)、
      skill.csv(station,required_per_shift,share)、config.json(window,k_high,color_batch)
用法：python3 weekly.py [配置包] [月份] [--apply]   默认 data/ 10，不加 --apply 不回写月模型
输出：output/weekly_sequence.csv、output/weekly_summary.csv（示例数据）"""
import csv, json, os
import data_loader as dl, engine, report as rp
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "output")
DEF_CFG = {"window": 8, "k_high": 5, "color_batch": 200}   # 滑动窗口/高工时上限/颜色批量（示例 ⚠ 需 IE 工艺确认）
def _o(base, name):
    p = os.path.join(base, name)
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []
def load_meta(base):
    """车型属性（工时等级/颜色）；缺省给示例属性"""
    ms = _o(base, "models.csv")
    if not ms:
        ms = [{"model": m, "config_load": ("high" if i == 0 else "low"), "color": f"C{i+1}"}
              for i, m in enumerate(["V446K", "V451", "V452"])]
    cb = {r["color"]: int(r["batch"]) for r in _o(base, "color_batch.csv")}
    return {r["model"]: r for r in ms}, cb, _o(base, "skill.csv"), {**DEF_CFG, **(json.load(open(os.path.join(base, "config.json"), encoding="utf-8")) if os.path.exists(os.path.join(base, "config.json")) else {})}
def weekly_volumes(plan, d, month):
    """该月 TCF 产量按车型需求占比分摊"""
    r = next(r for r in plan if r["shop"] == d["shops"][-1] and r["month"] == month)
    dm = {m: q for (t, m), q in d["demand"].items() if t == month}
    tot = sum(dm.values()) or 1
    return r, {m: r["volume"] * dm[m] / tot for m in dm}, r["shifts"]
def _units_by_color(vol, meta):
    """按车型自己的颜色成块。"""
    by = {}
    for m, q in vol.items():
        by.setdefault(meta[m]["color"], []).extend([m] * int(q))
    return by
def build_sequence(vol, meta, colors, cfg, mode="color"):
    """贪心：块内窗口将超限时改排低工时。seq 按车型颜色交错；color 每种颜色连续成块。"""
    W, K = cfg["window"], cfg["k_high"]
    blocks = [("_", [m for m, q in vol.items() for _ in range(int(q))])] if mode == "seq" else list(_units_by_color(vol, meta).items())
    built = []
    for color, flat in blocks:
        rem = {}
        for m in flat: rem[m] = rem.get(m, 0) + 1
        local = []
        while sum(rem.values()):
            win_hi = sum(1 for mm in local[-(W-1):] if meta[mm]["config_load"] == "high")
            cands = [m for m, c in rem.items() if c]
            hi = [m for m in cands if meta[m]["config_load"] == "high"]
            lo = [m for m in cands if meta[m]["config_load"] != "high"]
            pool = hi if (win_hi + 1 <= K and hi) else (lo or cands or hi)
            m = max(pool, key=lambda x: (rem[x], x))
            rem[m] -= 1
            local.append(m)
        built.append((color, local))
    if mode == "seq":
        return [(m, meta[m]["color"]) for m in built[0][1]]
    return [(m, color) for color, local in built for m in local]
def check_sequence(seq, meta, cfg):
    """校验：滑动窗口高工时超限窗口数、颜色切换次数"""
    W, K = cfg["window"], cfg["k_high"]
    hi = [1 if meta[m]["config_load"] == "high" else 0 for m, _ in seq]
    viol = sum(1 for i in range(len(seq)-W+1) if sum(hi[i:i+W]) > K)
    changes = sum(1 for i in range(1, len(seq)) if seq[i][1] != seq[i-1][1])
    return viol, changes
def feedback_caps(vol, meta, viol, month):
    """序列超限时，从高工时车型扣减该月槽位上限。无超限不回写。"""
    if not viol: return []
    caps = {m: int(vol[m]) for m in vol}
    left = int(viol)
    for m in sorted(vol, key=lambda x: (meta[x]["config_load"] != "high", -vol[x])):
        if left <= 0: break
        take = min(caps[m], left)
        caps[m] -= take
        left -= take
    return [dict(model=m, month=month, cap=caps[m]) for m in caps]
def skill_check(sk, plan_row):
    """技能矩阵：可用持证人数 = 该班总定员 × 该工位持证比例"""
    shift = int(plan_row["shifts"]); heads = plan_row.get("total_heads", plan_row.get("heads", 0))
    rows = []
    for r in sk:
        share = float(r.get("share") or 0.3); need = float(r["required_per_shift"]) * shift
        avail = heads * share
        rows.append(dict(工位=r["station"], 班次=shift, 定员=heads, 持证比例=share, 每班需求=round(need, 1),
                         可用=round(avail, 1), 缺口=round(max(0.0, need-avail), 1), 状态="不足" if need > avail else "OK"))
    return rows
def _merge_slot_cap(base, caps):
    """把该月槽位上限写进配置包。同车型同月覆盖，其它月份保留。"""
    path = os.path.join(base, "slot_cap.csv")
    old = _o(base, "slot_cap.csv")
    keep = [r for r in old if not any(r.get("model") == c["model"] and str(r.get("month")) == str(c["month"]) for c in caps)]
    rows = keep + [dict(model=c["model"], month=c["month"], cap=c["cap"]) for c in caps]
    rp.write_csv(path, rows)
def main(base="data", month=10, apply=False):
    d = dl.load(os.path.join(H, base)); meta, cb, sk, cfg = load_meta(os.path.join(H, base))
    colors = sorted({meta[m]["color"] for m in d["models"]})
    _st, _obj, plan, _cost, _out, _sh, _v = engine.solved(d)
    row, vol, shift = weekly_volumes(plan, d, month)
    res = {}
    for mode, tag in (("seq", "方案A_序列优先"), ("color", "方案B_颜色优先")):
        seq = build_sequence(vol, meta, colors, cfg, mode)
        viol, ch = check_sequence(seq, meta, cfg)
        res[tag] = (seq, dict(月份=month, 方案=tag, 班次=int(shift), 计划产量=row["volume"],
                              **{f"产量_{m}": int(vol.get(m, 0)) for m in d["models"]},
                              高工时台数=sum(1 for m, _ in seq if meta[m]["config_load"] == "high"),
                              颜色切换次数=ch, 序列超限窗口数=viol, 窗口=f"{cfg['window']}台/{cfg['k_high']}高工时"))
    best = "方案A_序列优先" if res["方案A_序列优先"][1]["序列超限窗口数"] == 0 else "方案B_颜色优先"
    seq = res[best][0]
    rp.write_csv(os.path.join(OUT, "weekly_sequence.csv"),
                 [dict(序号=i+1, 车型=m, 颜色=c, 工时等级=meta[m]["config_load"], 月=month) for i, (m, c) in enumerate(seq)])
    rp.write_csv(os.path.join(OUT, "weekly_summary.csv"), [res[k][1] for k in res])
    print("\n=== 周计划（示例数据）：序列规则 vs 换色批量的权衡 ===")
    for k in res: print(" ", res[k][1])
    print(f"→ 选用 {best}；序列文件 output/weekly_sequence.csv（{len(seq)} 台）")
    caps = feedback_caps(vol, meta, res[best][1]["序列超限窗口数"], month)
    if not caps:
        print("序列未超限，月模型未重解，无需回写槽位上限")
    else:
        rp.write_csv(os.path.join(OUT, "slot_feedback.csv"), caps)
        pkg = os.path.join(H, base)
        if apply:
            _merge_slot_cap(pkg, caps)
            d2 = dl.load(pkg); st2, obj2, _plan2, _cost2, _out2, _sh2, _v2 = engine.solved(d2)
            print(f"已把槽位上限写入 {base}/slot_cap.csv 并重解一次：{st2}，目标 {round((obj2 or 0)/1e4)} 万元")
        else:
            print("序列超限，已写 output/slot_feedback.csv。月模型未重解，槽位上限未回写。确认后加 --apply 才会写入配置包并重解")
    if sk:
        print("\n=== 技能矩阵覆盖 ===")
        for g in skill_check(sk, row): print(" ", g)
if __name__ == "__main__":
    import sys
    apply = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--apply"]
    main(args[0] if args else "data", int(args[1]) if len(args) > 1 else 10, apply)