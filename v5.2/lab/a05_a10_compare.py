"""假设登记表 A05–A10 按天层对比：单开 / 全开，月需求 10,000 与 6,000（示例数据，模拟口径，⚠ 全部示例值）
用法：python3 lab/a05_a10_compare.py [--no-cache]  → output/a05_a10_compare.csv、output/A05-A10按天层对比.html"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import copy, html, json, os, sys, time, multiprocessing as mp
import data_loader as dl, daily as dy

EX = dict(dy.load_cfg(None)["_A05_A10_示例"])   # ⚠ 示例值，见 daily_config.json
MIX = EX.pop("jph_options.csv:mix_eff"); EX.pop("_说明", None)
def tier(d, s, jph): return next(i for i, o in enumerate(d["jph"][s]) if o["jph"] == float(jph))

SCEN = [("Q10000", "月需求 10,000 台 · 每天可少开班（默认口径）", dict(monthly_demand=10000)),
        ("Q6000", "月需求 6,000 台 · 每天可少开班（默认口径）", dict(monthly_demand=6000)),
        ("Q6000整班", "月需求 6,000 台 · 整班开/整天停（2 班定员）", dict(monthly_demand=6000, fix_crew={"BIW": 2, "PNT": 2}, same_shift_as_crew=True))]
# (键, 名称, 对照键, 说明)
SET = [("base", "基线（A05–A10 全关）", None, "当前默认"),
       ("A05", "A05 招聘提前期 1 月", "base", "上月定员 JPH36×2，本月不能加人"),
       ("p36", "对照：上月 JPH36（只有 A04 换档成本）", "base", "A06、全开的对照行：上月档定了，选别的档就有换档成本"),
       ("A06", "A06 学习曲线 +1 天", "p36", "上月 JPH36 档；换档才生效；与 p36 比"),
       ("A07", "A07 混线有效系数 0.95", "base", "名义 JPH × 0.95"),
       ("A08", "A08 每月 1 个 PM 日", "base", "10-17（周三）停线"),
       ("A09", "A09 JIT 日波动罚金", "base", "带宽 10%，超出 100 元/台"),
       ("A10", "A10 启线质量 3 万元/次", "base", "每次启线计一次"),
       ("ALL", "全开（A05–A10）", "p36", "以上六项同时打开；与 p36 比（扣掉 A04 换档成本的影响）"),
       ("ALLb", "全开（A05–A10，对基线）", "base", "同上，与基线比（含 A04 换档成本）"),
       ("p30", "对照：上月 JPH30（只有 A04 换档成本）", "base", "说明 A06 需要换档才起作用"),
       ("A06p30", "A06 +1 天（上月 JPH30）", "p30", "与上一行比"),
       ("A05p30", "A05 提前 1 月（上月 JPH30×2）", "base", "上月人数少于基线所需；人不够时出现缺货（缺货台见右列，缺货罚金不在运营成本里）")]

def make(d, key):
    c = {}; e = d
    if key in ("A05", "ALL", "ALLb"): c.update(hire_lead_months=EX["hire_lead_months"], prev_crew=EX["prev_crew"])
    if key == "p36": c.update(prev_jph_tier={s: tier(d, s, 36) for s in ("BIW", "PNT")})
    if key in ("A06", "ALL", "ALLb"): c.update(learning_extra_lost_days=EX["learning_extra_lost_days"], prev_jph_tier={s: tier(d, s, 36) for s in ("BIW", "PNT")})
    if key in ("A08", "ALL", "ALLb"): c.update(pm_dates=EX["pm_dates"])
    if key in ("A09", "ALL", "ALLb"): c.update(jit_swing_penalty_per_unit=EX["jit_swing_penalty_per_unit"], jit_free_swing_ratio=EX["jit_free_swing_ratio"])
    if key in ("A10", "ALL", "ALLb"): c.update(restart_quality_cost=EX["restart_quality_cost"])
    if key in ("A07", "ALL", "ALLb"):
        e = copy.deepcopy(d)
        for s in e["jph"]:
            for o in e["jph"][s]: o["mix_eff"] = MIX
    if key == "p30": c.update(prev_jph_tier={s: tier(d, s, 30) for s in ("BIW", "PNT")})
    if key == "A06p30": c.update(prev_jph_tier={s: tier(d, s, 30) for s in ("BIW", "PNT")}, learning_extra_lost_days=EX["learning_extra_lost_days"])
    if key == "A05p30": c.update(hire_lead_months=EX["hire_lead_months"], prev_crew={"BIW": [30, 2], "PNT": [30, 2]})
    return e, c

NEW = ("复产质量", "JIT波动", "JPH换档")
def one(job):
    sk, key, strat, use_cache = job; d = dl.load(None); base_cfg = dy.load_cfg(None)
    sc = dict(next(x[2] for x in SCEN if x[0] == sk)); e, c = make(d, key)
    cfg = dict(base_cfg, **sc, **c); r = dy.solve_cached(e, cfg, strat, None, False, use_cache); k = r["kpi"]
    return dict(情景=sk, 设定=key, 策略=strat, 状态=k["状态"], 运营成本_万元=k["运营成本_万元"], 单车_元=k["单车_元"], 人工_万元=k["人工_万元"], 能源_万元=k["能源_万元"],
                焊装=k["焊装定员班次"], 涂装=k["涂装定员班次"], 焊装开工天=k["焊装开工天"], 涂装开工天=k["涂装开工天"], 启炉=k["涂装启炉次数"], 缺货台=k["缺货台"],
                **{f"{n}_万元": round(r["cost"].get(n, 0) / 1e4, 1) for n in NEW}, 求解秒=k["求解秒"])

def esc(x): return html.escape(str(x))
def page(rows, path):
    R = {(r["情景"], r["设定"], r["策略"]): r for r in rows}
    css = "body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;max-width:1180px;margin:24px auto;padding:0 16px;color:#222;line-height:1.55}table{border-collapse:collapse;width:100%;margin:10px 0 22px;font-size:13px}th,td{border:1px solid #ccc;padding:5px 7px;text-align:right}th{background:#f2f4f7}td.l,th.l{text-align:left}.flip{background:#fde2e1;font-weight:600}.tag{display:inline-block;background:#fff3cd;border:1px solid #e0c36a;border-radius:4px;padding:1px 6px;font-size:12px}h2{border-left:5px solid #2b6cb0;padding-left:8px;margin-top:30px}.note{color:#555;font-size:13px}"
    H = [f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>A05–A10 按天层对比（示例数据）</title><style>{css}</style><body>",
         "<h1>假设 A05–A10 按天层对比：单开 / 全开</h1>",
         "<p><span class='tag'>示例数据</span> <span class='tag'>模拟口径</span> 全部数字来自 v5.2 示例参数（daily_config.json、jph_options.csv 等），⚠ 不是工厂实测，也不是任何公司的真实成本。"
         f"生成时间 {time.strftime('%Y-%m-%d %H:%M')}（北京时间）。</p>",
         "<p class='note'>运营成本 = 模型自主排产的月成本（不含缺货惩罚）。开停策略节省 = 「每个工作日都开」成本 − 模型自主排产成本。推荐方案 = 模型自主排产选的焊装/涂装定员班次与开工天数；定员班次与对照不同才标红为「翻转」（开工天数变化只显示）。"
         "求解器 MIP 相对间隙 0.1%，约 1 万元以内的差别在求解精度内。</p>"]
    summ = []
    for sk, title, _ in SCEN:
        b = R.get((sk, "base", "optimal")); bw = R.get((sk, "base", "weekdays"))
        H.append(f"<h2>{esc(title)}</h2><table><tr><th class='l'>设定</th><th class='l'>说明</th><th>运营成本<br>万元/月</th><th>比对照<br>万元</th><th class='l'>推荐方案（焊装 / 涂装 · 开工天）</th><th>翻转</th>"
                 "<th>每工作日都开<br>万元</th><th>开停策略节省<br>万元</th><th>节省变化<br>万元</th><th>节省变化<br>%</th><th>复产质量</th><th>JIT波动</th><th>JPH换档</th><th>缺货台</th></tr>")
        best = None; bsv = round(bw["运营成本_万元"] - b["运营成本_万元"], 1) if b and bw else 0; by_sv = abs(bsv) >= 1   # 基线节省≈0 时按运营成本排
        for key, name, ref, note in SET:
            o = R.get((sk, key, "optimal")); w = R.get((sk, key, "weekdays"))
            if not o or not w: continue
            ro = R.get((sk, ref, "optimal")) if ref else o; rw = R.get((sk, ref, "weekdays")) if ref else w
            plan = f"{o['焊装']} / {o['涂装']} · {o['焊装开工天']}/{o['涂装开工天']} 天"
            rplan = f"{ro['焊装']} / {ro['涂装']} · {ro['焊装开工天']}/{ro['涂装开工天']} 天"
            flip = (o['焊装'], o['涂装']) != (ro['焊装'], ro['涂装'])   # 翻转 = 推荐的定员班次变了；开工天数变化只显示不算翻转
            sv = round(w["运营成本_万元"] - o["运营成本_万元"], 1); rsv = round(rw["运营成本_万元"] - ro["运营成本_万元"], 1)
            dsv = round(sv - rsv, 1); pct = "—（对照节省≈0）" if abs(rsv) < 1 else f"{dsv / rsv * 100:+.0f}%"
            dc = round(o["运营成本_万元"] - ro["运营成本_万元"], 1)
            m = dsv if by_sv else dc
            if key in ("A05", "A06", "A07", "A08", "A09", "A10") and (best is None or abs(m) > abs(best[3])): best = (name, dc, dsv, m)
            H.append(f"<tr><td class='l'>{esc(name)}</td><td class='l'>{esc(note)}</td><td>{o['运营成本_万元']:,.1f}</td><td>{'' if key=='base' else f'{dc:+,.1f}'}</td>"
                     f"<td class='l{' flip' if flip else ''}'>{esc(plan)}</td><td class='{'flip' if flip else ''}'>{'是' if flip else '否'}</td><td>{w['运营成本_万元']:,.1f}</td><td>{sv:,.1f}</td>"
                     f"<td>{'' if key=='base' else f'{dsv:+,.1f}'}</td><td>{'' if key=='base' else pct}</td><td>{o['复产质量_万元']}</td><td>{o['JIT波动_万元']}</td><td>{o['JPH换档_万元']}</td><td>{o['缺货台']}</td></tr>")
        H.append("</table>")
        if best: summ.append(f"<li>{esc(title)}：{'对开停策略节省' if by_sv else '对运营成本（这里基线开停节省≈0）'}影响最大的单项是 <b>{esc(best[0])}</b>（运营成本 {best[1]:+,.1f} 万元/月，开停节省 {best[2]:+,.1f} 万元/月）。</li>")
    H.append("<h2>一句话结论（示例数据，模拟口径）</h2><ul>" + "".join(summ) + "<li>只在 6 个按示例值单开的设定里比较；p30、A06p30、A05p30 是换上月假设后的机制演示，不参与排名。</li></ul>")
    H.append("<h2>参数怎么进模型（按天层）</h2><table><tr><th class='l'>编号</th><th class='l'>参数（默认 = 关闭）</th><th class='l'>做法</th><th class='l'>近似点</th></tr>" + "".join(
        f"<tr><td class='l'>{a}</td><td class='l'>{esc(b)}</td><td class='l'>{esc(c)}</td><td class='l'>{esc(e)}</td></tr>" for a, b, c, e in [
        ("A05", "hire_lead_months=0，prev_crew=null", "提前期 ≥ 1 月且给出上月定员时，本月定员人数（直接+间接）≤ 上月", "单月模型只能表达「本月不能加人」；加班提前量没建；月度模型仍用 head_up（每月增幅上限）近似"),
        ("A06", "learning_extra_lost_days=0", "换档损失天数 = jph_switch.csv 的 lost_days + N", "只有 prev_jph_tier 与本月档不同才生效；不是逐日爬坡曲线"),
        ("A07", "jph_options.csv mix_eff=1.0", "有效 JPH = 名义 JPH × 有效系数，月度与按天产能都乘", "一个系数代表车型组合，不随车型比例变"),
        ("A08", "pm_dates=[]", "PM 日焊装、涂装都不开；总装需求摊到其余工作日；KPI 多一列 PM停线天", "按全厂停线处理；只认本月日期，不核对年份；PM 当天人工按停工日处理"),
        ("A09", "jit_swing_penalty_per_unit=0，jit_free_swing_ratio=0", "焊装相邻两个工作日的产量差，超出免费带宽（日均需求 × 比例）的部分按元/台计罚", "选罚金不选硬上限：硬上限遇到整天停线会直接无解或被迫缺货；罚金可直接读成加急/调度费。周末和 PM 日视为已提前通知，不计"),
        ("A10", "restart_quality_cost=0", "每次启线（前一天不开、当天开）计一笔，科目「复产质量」", "周末后的周一启线也计（各策略都有）；月初第 1 天不计")]) + "</table>")
    H.append("<p class='note'>来源：v5.2/lab/a05_a10_compare.py；明细 CSV：output/a05_a10_compare.csv。⚠ 示例值见 daily_config.json 的 _A05_A10_示例。</p></body></html>")
    open(path, "w", encoding="utf-8").write("\n".join(H))

if __name__ == "__main__":
    uc = "--no-cache" not in sys.argv
    jobs = [(sk, key, st, uc) for sk, _, _ in SCEN for key, *_ in SET for st in ("optimal", "weekdays")]
    t0 = time.time(); out = os.path.join(dy.H, "output"); part = os.path.join(out, "a05_a10_compare_rows.jsonl")   # 逐条落盘，中断后重跑会跳过已完成的
    done = {}
    if os.path.exists(part):
        for ln in open(part, encoding="utf-8"):
            if ln.strip(): r = json.loads(ln); done[(r["情景"], r["设定"], r["策略"])] = r
    todo = [j for j in jobs if j[:3] not in done]; print("已完成", len(done), "待跑", len(todo), flush=True)
    with mp.get_context("spawn").Pool(3) as p:
        for r in p.imap_unordered(one, todo):
            done[(r["情景"], r["设定"], r["策略"])] = r
            with open(part, "a", encoding="utf-8") as fh: fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(len(done), "/", len(jobs), r["情景"], r["设定"], r["策略"], r["运营成本_万元"], flush=True)
    rows = [done[j[:3]] for j in jobs]
    dy.wcsv(os.path.join(out, "a05_a10_compare.csv"), rows)
    page(rows, os.path.join(out, "A05-A10按天层对比.html"))
    for r in rows: print(r)
    print("用时", round(time.time() - t0), "秒")
