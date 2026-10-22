"""v5.1 图表（matplotlib + Noto Sans CJK，示例数据）：输出 output/v5.1/图*.png；只重画图不重算（读 CSV / 缓存）"""
import csv, os, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import cjkfont; cjkfont.use()
import data_loader as dl, energy as E, daily
from scenarios import apply_knobs
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "output", "v5.1")
def rd(n): return list(csv.DictReader(open(os.path.join(OUT, n), encoding="utf-8-sig")))
def fig_tou(d):
    fig, ax = plt.subplots(figsize=(13, 5.5)); x = range(24)
    for ver, c, off in (("2026", "#c62828", -0.2), ("2024", "#90a4ae", 0.2)):
        p = E.hour_prices(apply_knobs(d, {"tou_version": ver}), 10); ax.bar([h + off for h in x], p, width=0.4, color=c, label=f"{ver} 版（10 月，110kV）")
    for a, b, nm, col in ((0, 8, "夜班", "#e3f2fd"), (8, 16, "早班", "#fffde7"), (16, 24, "中班", "#fce4ec")):
        ax.axvspan(a - 0.5, b - 0.5, color=col, zorder=0); ax.text((a + b) / 2 - 0.5, 1.02, f"{nm} {a}–{b}点 均价 {sum(E.hour_prices(d,10)[a:b])/8:.3f}", ha="center", fontsize=10)
    ax.set_xticks(list(x)); ax.set_ylim(0, 1.1); ax.set_xlabel("小时"); ax.set_ylabel("元/kWh"); ax.legend(loc="upper left")
    ax.set_title("浙江分时电价：2026 新政（浙发改价格〔2026〕112号）vs 2024 版，春秋季 110kV 代理购电", fontsize=13); fig.tight_layout(); fig.savefig(os.path.join(OUT, "图1_分时电价与班次.png"), dpi=130); plt.close(fig)
def fig_strategy():
    s = rd("daily_strategy_summary.csv"); names = [r["策略"].replace("（", "\n（") for r in s]
    fig, ax = plt.subplots(figsize=(13, 6)); bot = [0] * len(s)
    for k, c in (("人工_万元", "#1565c0"), ("能源_万元", "#ef6c00"), ("库存_万元", "#2e7d32")):
        v = [float(r[k]) for r in s]; ax.bar(names, v, bottom=bot, color=c, label=k.replace("_万元", "")); bot = [a + b for a, b in zip(bot, v)]
    for i, r in enumerate(s): ax.text(i, bot[i] + 10, f"{float(r['运营成本_万元']):,.0f} 万元\n单车 {r['单车_元']} 元", ha="center", fontsize=10)
    ax.set_ylabel("万元/月"); ax.set_ylim(0, max(bot) * 1.15); ax.legend()
    ax.set_title("按天排产：焊装+涂装 10,000 台/月 各策略月成本（示例数据，暂定参数）", fontsize=13); fig.tight_layout(); fig.savefig(os.path.join(OUT, "图2_策略成本对比.png"), dpi=130); plt.close(fig)
def fig_buffer():
    fig, ax = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for s, c in (("continuous", "#757575"), ("sync", "#1565c0"), ("optimal", "#c62828"), ("two_shift", "#2e7d32")):
        p = os.path.join(OUT, f"daily_schedule_{s}.csv")
        if not os.path.exists(p): continue
        r = rd(f"daily_schedule_{s}.csv"); ax[0].plot([int(x["日"]) for x in r], [int(x["白车身缓存"]) for x in r], marker="o", ms=3, color=c, label=daily.NAMES[s])
        if s == "optimal":
            for x in r:
                st = x["PNT_状态"]; col = "#ef9a9a" if "3班" in st else "#ffcc80" if "2班" in st else "#fff59d" if "1班" in st else "#b0bec5" if st == "停炉" else "#eceff1"
                ax[1].bar(int(x["日"]), int(x["PNT_产量"]) or 15, color=col, edgecolor="#607d8b")
                ax[1].text(int(x["日"]), (int(x["PNT_产量"]) or 15) + 8, st.replace("JPH", "").replace("班", ""), ha="center", fontsize=7, rotation=90)
    ax[0].axhline(daily.load_cfg()["biw_buffer_max"], ls="--", color="#c62828"); ax[0].text(1, daily.load_cfg()["biw_buffer_max"] + 8, "白车身库容上限（暂定）", color="#c62828")
    ax[0].set_ylabel("白车身缓存（台）"); ax[0].legend(fontsize=9, ncol=2); ax[0].set_title("白车身缓存日轨迹（上）与模型自主排产的涂装每日状态/产量（下）（示例数据）", fontsize=13)
    ax[1].set_ylabel("涂装产量（台/天）"); ax[1].set_xlabel("日（第 6、7、13、14…天为周末）"); ax[1].set_ylim(0, 620)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "图3_缓存轨迹与涂装开停.png"), dpi=130); plt.close(fig)
def fig_monthly_energy():
    def cost(p): return {r["科目"]: float(r["金额_元"]) for r in csv.DictReader(open(p, encoding="utf-8-sig"))}
    old = os.path.join(H, "..", "v5", "output", "cost_基准.csv")
    if not os.path.exists(old):
        print("跳过图4：没有", old); return
    a = cost(old); b = cost(os.path.join(H, "output", "cost_基准.csv"))
    ks = ["能源固定", "能源变动", "能源-电(运行)", "能源-电(待机)", "能源-天然气", "启停能耗", "需量电费"]
    fig, ax = plt.subplots(figsize=(12, 5.5)); bot = [0, 0]; cols = ["#90a4ae", "#ffb74d", "#e65100", "#8d6e63", "#1565c0", "#6a1b9a", "#2e7d32"]
    for k, c in zip(ks, cols):
        v = [a.get(k, 0) / 1e4, b.get(k, 0) / 1e4]
        if not any(v): continue
        ax.bar(["v5（单一电价 0.75，无气/启停/需量）", "v5.1（分时电价+气+启停+需量）"], v, bottom=bot, color=c, label=k)
        for i in (0, 1):
            if v[i] > 150: ax.text(i, bot[i] + v[i] / 2, f"{k}\n{v[i]:,.0f}", ha="center", va="center", fontsize=9, color="white")
        bot = [x + y for x, y in zip(bot, v)]
    for i in (0, 1): ax.text(i, bot[i] + 60, f"合计 {bot[i]:,.0f} 万元", ha="center", fontsize=11)
    ax.set_ylabel("万元/年"); ax.set_ylim(0, max(bot) * 1.12); ax.legend(fontsize=9, loc="upper left")
    ax.set_title("月度模型全年能源口径：v5 → v5.1（基准场景，示例数据）", fontsize=13); fig.tight_layout(); fig.savefig(os.path.join(OUT, "图4_月度能源口径对比.png"), dpi=130); plt.close(fig)
def fig_jph(d):
    rows = []
    for o in d["jph"]["PNT"]:
        for k in (1, 2, 3):
            cap = o["jph"] * d["shift"][k]["eff_hours_per_shift"] * k * 21 * 0.9
            if cap < 9000: continue
            rows.append((f"JPH{int(o['jph'])}×{k}班", E.estimate_per_unit(d, "PNT", o, k, 10, 9000)))
    fig, ax = plt.subplots(figsize=(12, 5.5)); bot = [0] * len(rows)
    for k, c in (("能源-电(运行)", "#e65100"), ("能源-电(待机)", "#8d6e63"), ("能源-天然气", "#1565c0"), ("启停能耗", "#6a1b9a"), ("单车变动", "#9e9e9e")):
        v = [r.get(k, 0) for _, r in rows]; ax.bar([n for n, _ in rows], v, bottom=bot, color=c, label=k); bot = [a + b for a, b in zip(bot, v)]
    for i, b in enumerate(bot): ax.text(i, b + 3, f"{b:.0f} 元/台", ha="center")
    ax.set_ylabel("元/台"); ax.legend(fontsize=9); ax.set_title("涂装单车能源估算：月产 9,000 台时不同 JPH×班次（energy.estimate_per_unit，暂定参数）", fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "图5_JPH与单车能源.png"), dpi=130); plt.close(fig)
def fig_shadow():
    r = rd("daily_buffer_shadow.csv"); fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot([int(x["库容_台"]) for x in r], [float(x["运营成本_万元"]) for x in r], marker="o", color="#c62828")
    for x in r: ax.annotate(f"{x['每台库容月节省_元']}", (int(x["库容_台"]), float(x["运营成本_万元"])), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
    ax.set_xlabel("白车身库容上限（台）"); ax.set_ylabel("运营成本（万元/月）"); ax.grid(alpha=.3)
    ax.set_title("白车身库容灵敏度（模型自主排产，10,000 台/月；标注=每台库容每月节省 元）", fontsize=12); fig.tight_layout(); fig.savefig(os.path.join(OUT, "图6_库容影子价格.png"), dpi=130); plt.close(fig)
if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); d = dl.load()
    for f in (lambda: fig_tou(d), fig_strategy, fig_buffer, fig_monthly_energy, lambda: fig_jph(d), fig_shadow): f()
    print("图已输出到", OUT)
