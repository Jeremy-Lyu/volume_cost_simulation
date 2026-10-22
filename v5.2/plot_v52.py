"""v5.2 图（示例数据）：月度 v5.1→v5.2 科目差、JPH 档月度轨迹、派遣比敏感性、库容影子价格"""
import csv, os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cjkfont; cjkfont.use()
H = os.path.dirname(os.path.abspath(__file__)); V1 = os.path.join(H, "..", "v5.1", "output"); V2 = os.path.join(H, "output"); OUT = os.path.join(V2, "v5.2"); os.makedirs(OUT, exist_ok=True)
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig")))
def cost(p): return {r["科目"]: float(r["金额_元"]) / 1e4 for r in rd(p)}
def fig_bridge():
    a, b = cost(os.path.join(V1, "cost_基准.csv")), cost(os.path.join(V2, "cost_基准.csv"))
    ks = [k for k in dict.fromkeys(list(a) + list(b)) if abs(b.get(k, 0) - a.get(k, 0)) >= 1 and "惩罚" not in k]
    ks.sort(key=lambda k: b.get(k, 0) - a.get(k, 0)); dv = [b.get(k, 0) - a.get(k, 0) for k in ks]
    fig, ax = plt.subplots(figsize=(13, 6.5)); ax.barh(ks, dv, color=["#2e7d32" if x < 0 else "#c62828" for x in dv])
    for i, x in enumerate(dv): ax.text(x, i, f" {x:+,.0f}", va="center", ha="left" if x >= 0 else "right", fontsize=10)
    ta, tb = sum(v for k, v in a.items() if "惩罚" not in k), sum(v for k, v in b.items() if "惩罚" not in k)
    ax.axvline(0, color="k", lw=.8); ax.set_xlabel("万元/年（v5.2 − v5.1）")
    ax.set_title(f"月度基准：v5.1 → v5.2 按科目变化（合计 {ta:,.0f} → {tb:,.0f} 万元，{tb-ta:+,.0f}；示例数据）", fontsize=13)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "图7_v51_v52科目变化.png"), dpi=120); plt.close(fig)
def fig_tiers():
    fig, axs = plt.subplots(1, 4, figsize=(18, 4.8), sharey=False)
    for ax, s in zip(axs, ("STP", "BIW", "PNT", "TCF")):
        for v, p, c in (("v5.1", V1, "#90a4ae"), ("v5.2", V2, "#1565c0")):
            r = [x for x in rd(os.path.join(p, "plan_基准.csv")) if x["shop"] == s]; m = [int(x["month"]) for x in r]; j = [float(x["jph"]) for x in r]
            n = sum(1 for i in range(1, len(j)) if j[i] != j[i - 1])
            ax.step(m, j, where="mid", color=c, lw=2.5 if v == "v5.2" else 4, alpha=.9, label=f"{v}（换档 {n} 次）")
        ax.set_title(s, fontsize=13); ax.set_xticks(range(1, 13)); ax.set_xlabel("月"); ax.legend(fontsize=9); ax.set_ylim(18, 54)
    axs[0].set_ylabel("JPH 档"); fig.suptitle("JPH 档月度轨迹：加入换档成本（30 万元/次 + 2 天产出 ⚠）后换档明显减少（示例数据）", fontsize=14)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "图8_JPH换档轨迹.png"), dpi=120); plt.close(fig)
def fig_sweep():
    p = os.path.join(V2, "v5.1", "daily_flex_sweep.csv")
    if not os.path.exists(p): return
    R = rd(p); fig, ax = plt.subplots(1, 2, figsize=(17, 6))
    for kj, c in (("每天可少开班", "#1565c0"), ("整班开/整天停", "#c62828")):
        o = [r for r in R if r["口径"] == kj and r["白车身库容"] == "600" and r["策略"] == "模型自主排产"]
        w = [r for r in R if r["口径"] == kj and r["策略"].startswith("每个工作日")]
        if not o: continue
        x = [int(r["派遣比"].rstrip("%")) for r in o]
        ax[0].plot(x, [float(r["运营成本_万元"]) for r in o], "o-", color=c, lw=2, label=f"{kj}：模型自主排产")
        ax[0].plot([int(r["派遣比"].rstrip("%")) for r in w], [float(r["运营成本_万元"]) for r in w], "s--", color=c, alpha=.6, label=f"{kj}：每个工作日都开")
        for r, xx in zip(o, x): ax[0].annotate((f"开{r['涂装开工天']}天\n省{r['比每工作日都开省_万元']}万" if float(r['比每工作日都开省_万元']) > 6 else f"开{r['涂装开工天']}天\n≈0（求解精度内）"), (xx, float(r["运营成本_万元"])), textcoords="offset points", xytext=(6, 6), fontsize=9, color=c)
    ax[0].set_xlabel("派遣/临时工占比 %"); ax[0].set_ylabel("月运营成本 万元"); ax[0].legend(fontsize=9); ax[0].set_title("月需求 6,000 台、2 班定员：开停策略 vs 每工作日都开", fontsize=12)
    bb = os.path.join(V2, "v5.1", "daily_buffer_bind.csv")
    o = sorted([r for r in R if r["口径"] == "整班开/整天停" and r["派遣比"] == "50%" and r["策略"] == "模型自主排产"] + (rd(bb) if os.path.exists(bb) else []), key=lambda r: int(r["白车身库容"]))
    x = [int(r["白车身库容"]) for r in o]
    ax[1].plot(x, [float(r["运营成本_万元"]) for r in o], "o-", color="#c62828", label="月运营成本（万元）")
    for r, xx in zip(o, x): ax[1].annotate(f"影子价格{float(r['库容影子价格_元每台月'] or 0):.0f}\n最高缓存{r['最高白车身缓存']}", (xx, float(r["运营成本_万元"])), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5)
    ax[1].set_ylim(min(float(r["运营成本_万元"]) for r in o) - 10, max(float(r["运营成本_万元"]) for r in o) + 10)
    ax[1].set_xlabel("白车身库容 台"); ax[1].set_ylabel("月运营成本 万元"); ax[1].legend(fontsize=9); ax[1].set_title("整班开/整天停、派遣 50%：库容 100–600 台影子价格均为 0（焊装涂装同日开停）", fontsize=11)
    fig.suptitle("派遣比敏感性（示例数据，⚠ 停工日发薪 70%/0%、借调 10% 为行业假设）", fontsize=14)
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "图9_派遣比敏感性.png"), dpi=120); plt.close(fig)
if __name__ == "__main__":
    fig_bridge(); fig_tiers(); fig_sweep(); print("ok", os.listdir(OUT))
