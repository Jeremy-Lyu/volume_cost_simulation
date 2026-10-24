"""v4 逻辑结构图：输入 → 加载/检查 → 场景旋钮 → 模型 → 求解/自检 → 报表输出 → 循环（依据 v4 实际代码，示例数据）"""
import os, sys; sys.path.insert(0, os.path.dirname(__file__))
from common import *
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "发布", "版本记录", "v4逻辑结构图.png")
fig = plt.figure(figsize=(36, 22)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.text(0.5, 0.977, "VCS 产量成本模拟器 v4 · 逻辑结构图（输入 → 计算 → 输出）", ha="center", fontsize=28, fontweight="bold")
ax.text(0.5, 0.955, "依据 v4 代码 data_loader / plant_check / scenarios / model_builder / report / golden 与 data/*.csv、output/*.csv ｜ 示例数据 ｜ "
        "⚠暂定 = 待业务确认参数 ｜ 【R1–R7】= 业务规则作用位置：R1 缓存=车间总量 R2 缺口可延期 R3 允许0班 R4 加班36h/人可突破 R5 加班价=时薪×倍数 R6 两班夜班补贴 R7 间接人工归人工", ha="center", fontsize=13.5, color="#555")
TOP, BOT = 0.93, 0.205
cols = [(0.008, 0.165, "① 输入表（配置包 data/）", "#1565c0"), (0.181, 0.150, "② 加载 · 检查 · 场景旋钮", "#00838f"),
        (0.339, 0.322, "③ model_builder.build()  混合整数规划", "#6a1b9a"), (0.669, 0.132, "④ 求解 · 自检 · 报表", "#ef6c00"),
        (0.809, 0.183, "⑤ 输出文件（output/）", "#2e7d32")]
for x, w, t, c in cols:
    ax.add_patch(plt.Rectangle((x, BOT), w, TOP-BOT, fc="none", ec=c, lw=2.2, ls="-"))
    box(ax, x, TOP-0.032, w, 0.032, t, fc=c, ec=c, fs=15, bold=True, tc="white")
# ---- ① 输入
inp = [("plant.json", "工厂ID·车间链 STP→BIW→PNT→TCF·版本"),
       ("demand.csv", "月×车型 需求"), ("calendar.csv", "月 工作日"), ("capacity_limit.csv", "车间×车型×月 产能上限"),
       ("jph_options.csv", "车间 JPH档·每班定员·运行kW"),
       ("shift_options.csv", "班次0/1/2/3·有效时长·班车·外包\nnight_shifts 0/0/1/1 ⚠暂定 R3 R6"),
       ("shop_params.csv", "单车kWh·OH·ot_max 36h/人·buffer_cap\nhold_cost·idle_fixed 30万 ⚠暂定 R1 R3 R4"),
       ("global_params.csv", "工资·电价·缺口惩罚3万·std_hours 174⚠\not_multiplier 1.5⚠·ot硬上限60h⚠\n超限溢价30⚠·夜班30元⚠·延期1500⚠·gap"),
       ("scenario_library.csv", "场景名·类别·knobs JSON"),
       ("data_source_map.csv", "参数→源系统→负责人·口径状态"),
       ("可选扩展表(缺表=不启用)", "mat_cost·margin·indirect·quality·ramp\nchangeover·carrier·shipping_cap·logistics\noee·attendance·asset·tooling… (plants/FULL_COST)")]
hs = [0.032, 0.025, 0.025, 0.028, 0.03, 0.045, 0.05, 0.072, 0.03, 0.03, 0.07]
y = TOP - 0.042
for (f, dsc), h in zip(inp, hs):
    y -= h
    box(ax, 0.013, y, 0.155, h-0.004, f"{f}\n{dsc}" if "\n" not in f else f, fc="#e3f2fd", ec="#1565c0", fs=12.3)
    y -= 0.004
# ---- ② 加载/检查/旋钮
x2, w2 = 0.186, 0.140
box(ax, x2, 0.735, w2, 0.15, "data_loader.load(data_dir)\n读取 CSV → 参数字典 d\nv4 缺省参数(⚠暂定)补齐\n自动补 0班行【R3】\nJPH 档按升序排序\nvalidate()：日历/产能完整、\n定员随JPH单调、36h≤硬上限", fc="#e0f7fa", ec="#00838f", fs=13.5)
box(ax, x2, 0.6, w2, 0.115, "plant_check.py\n结构 / 完整性 / 规则\n→ output/readiness_<厂>.md\n就绪度 L0–L3\n(TZ 示例 = L2)", fc="#e0f7fa", ec="#00838f", fs=13.5)
box(ax, x2, 0.375, w2, 0.205, "scenarios.apply_knobs(d, knobs)\ndemand_all / month / model / cell\navail 开动率系数 · down 停线天数\nsupply 零件供应上限\nelec · wage 单价系数\not → set_ot_cap 严格上限\n\ndata_loader.scenario(demand,\nelec, wage)  (run.py 用)\nwage↑ → 加班价自动联动【R5】", fc="#e0f7fa", ec="#00838f", fs=13)
box(ax, x2, 0.225, w2, 0.13, "cost_functions.py\n单元成本函数（被③调用）\nhours·capacity·ot_units\nlabor_breakdown【R6 R7】\not_rate = 时薪×倍数【R5】\nfixed_breakdown 0班→停线固定【R3】", fc="#f3e5f5", ec="#6a1b9a", fs=13)
for a, b in [((x2+w2/2, 0.735), (x2+w2/2, 0.715)), ((x2+w2/2, 0.6), (x2+w2/2, 0.58))]: arrow(ax, a, b, color="#00838f", lw=2.4)
arrow(ax, (0.168, 0.81), (x2, 0.81), lw=3); ax.text(0.1735, 0.822, "读取", fontsize=12, color="#1565c0")
# ---- ③ 模型
x3, w3 = 0.344, 0.312
box(ax, x3, 0.745, w3, 0.14,
    "决策变量（车间 s × JPH档 i × 班次 k × 月 t × 车型 m）\n"
    "y[s,i,k,t]∈{0,1}  每车间每月选 1 个「JPH档×班次」，k∈{0,1,2,3}；0班=整月停线，只挂最低档【R3】\n"
    "ot 常规加班(≤36h/人)　otx 超限加班【R4】　x[s,m,t] 各车间产量\n"
    "inv[s,m,t] 车间间缓存　bl 月末积压(延期)　short 流失(仅期末)【R2】\n"
    "(可选) ship/fginv 成品库·trips 物流趟次·st/on 换型·calloff/line_inv 叫料·co2over 碳", fc="#f3e5f5", ec="#6a1b9a", fs=15, ha="left")
box(ax, x3, 0.44, w3, 0.29,
    "关键约束\n"
    "• 选一：Σ_i,k y = 1（每车间每月）\n"
    "• 产能：Σ_m x ≤ Σ y·JPH×有效工时×产出系数 + JPH×(ot+otx)×产出系数\n"
    "     有效工时 = 每班时长×班次×(工作日−停线天)；车型上限 x ≤ capacity_limit\n"
    "• 加班：ot ≤ 36h×班次数；otx ≤ (60−36)h×班次数（每个班组都能加班）【R4】\n"
    "• 流平衡：上月缓存 + 上游产出 = 下游产出 + 本月缓存（冲压→焊装→涂装→总装）\n"
    "• 缓存总量：Σ_m inv[s,m,t] ≤ buffer_cap(s)（车间总量）【R1】\n"
    "• 积压平衡：上月积压 + 本月需求 = 本月交付 + 本月积压【R2】\n"
    "     期末积压 = 流失 short；非期末 short = 0\n"
    "• 可选：人数变化 head_change/head_up/head_dn · jph_step · shift_quarter · util_cap\n"
    "     （strategies.py 的稳定优先 / 保人力 策略开启）；supply 供应上限；fix_y 固定方案", fc="#f3e5f5", ec="#6a1b9a", fs=14.5, ha="left")
box(ax, x3, 0.225, w3, 0.2,
    "目标 min Σ 科目表达式 acc[科目]（目标与报表共用同一套表达式）\n"
    "人工(直接+间接+夜班补贴)【R7 R6】 · 福利社保 · 加班 · 超限加班溢价【R4】· 能源固定 · 能源变动\n"
    "班车 · 外包 · OH(固定常数+变动) · 停线固定【R3】 · 缓存持有 · 库存资金 · 成品持有\n"
    "延期成本 = 1500⚠暂定 × Σ非期末积压【R2】　缺口惩罚(流失) = 3万 × 期末积压\n"
    "(可选) −边际贡献 · 换型 · 物流-成品/入厂 · 碳配额 · 质量 · 保修与碳(仅总装) · 折旧×月数\n"
    "物料：只做口径，不进目标", fc="#ede7f6", ec="#4a148c", fs=14.5, ha="left")
arrow(ax, (x2+w2, 0.52), (x3, 0.6), color="#00838f", lw=3)
ax.text(0.312, 0.585, "参数字典 d", fontsize=12, color="#00838f")
arrow(ax, (x2+w2, 0.29), (x3, 0.32), color="#6a1b9a", lw=2)
# ---- ④ 求解/自检/报表
x4, w4 = 0.674, 0.122
box(ax, x4, 0.765, w4, 0.12, "model_builder.solve()\nHiGHS (gapRel 0.01%)\n无 HiGHS → CBC\n时间上限 solver_time_limit 60s\n→ 状态 + 目标值", fc="#fff3e0", ec="#ef6c00", fs=13.5)
box(ax, x4, 0.6, w4, 0.145, "report.extract()\n成本 = value(acc[科目])\nplan 明细逐车间×月\nreport.kpis()\n运营成本 = 目标 − 流失惩罚\n+ 边际贡献；单车 = 运营/产量", fc="#fff3e0", ec="#ef6c00", fs=13.2)
box(ax, x4, 0.43, w4, 0.15, "report.selfcheck() 守恒自检\n① Σ科目 = 目标\n② 每车间每月只选 1 方案\n③ 流平衡  ④ 缓存≤总量\n⑤ 交付 + 流失 = 需求\n不通过 → assert 报错", fc="#ffebee", ec="#c62828", fs=13.2)
box(ax, x4, 0.27, w4, 0.14, "golden.py 基线比对\n(run.py 末尾自动)\n总成本·产量·缺口·延期台月\n容差 0.05% 或 2 万\n改参数后 --update", fc="#ffebee", ec="#c62828", fs=13.2)
arrow(ax, (x3+w3, 0.81), (x4, 0.82), color="#6a1b9a", lw=3)
for a, b in [((x4+w4/2, 0.765), (x4+w4/2, 0.745)), ((x4+w4/2, 0.6), (x4+w4/2, 0.58)), ((x4+w4/2, 0.43), (x4+w4/2, 0.41))]:
    arrow(ax, a, b, color="#ef6c00", lw=2.4)
# ---- ⑤ 输出
x5, w5 = 0.814, 0.173
outs = [("scenario_summary.csv / results_summary.md", "每场景一行：总成本·运营成本·产量·流失(缺口)·延期台月\n加班h·超限加班h·平均缓存·停线车间月·单车·各车间JPH×班", 0.075),
        ("plan_<场景>.csv", "车间×月：jph·shifts(0=停线)·heads/total_heads\not_hours·ot_excess_hours·ot_per_head\ncapacity·volume·util·buffer_end", 0.075),
        ("cost_<场景>.csv", "科目·金额_元（人工含间接 R7；超限加班溢价；\n延期成本；缺口惩罚(流失)；停线固定）", 0.058),
        ("strategy_summary.csv + plan_策略_*.csv", "成本优先/稳定优先/保人力/需求+20%压力：成本·单车\n加班·超限·延期·人数最大月波动·利用率·缺口", 0.06),
        ("montecarlo_summary.csv", "固定 y，需求±8% 抽样 20 次：平均/P90 成本\n平均/最大缺口·有缺口样本占比·平均延期台月", 0.055),
        ("stress_library / downtime_sweep /\ndemand_ceiling.csv", "场景库冲击·焊装停线天数扫描·需求上限\n流失·延期·积压月份·瓶颈车间·三班车间月数", 0.06),
        ("readiness_*.md · plant_<厂>_backtest.csv", "就绪度 L0–L3；测算 vs 实际偏差（±5% ⚠暂定）", 0.045),
        ("account_map.csv · decision_log_template.csv", "模型科目→财务科目；决策单模板", 0.045)]
y = TOP - 0.04
for f, dsc, h in outs:
    y -= h
    box(ax, x5, y, w5, h-0.005, f"{f}\n{dsc}", fc="#e8f5e9", ec="#2e7d32", fs=12.3)
arrow(ax, (x4+w4, 0.67), (x5, 0.70), color="#2e7d32", lw=3)
# ---- 底部循环
ax.add_patch(plt.Rectangle((0.008, 0.02), 0.984, 0.165, fc="#fafafa", ec="#424242", lw=2))
box(ax, 0.008, 0.155, 0.984, 0.03, "⑥ 批量循环（同一套 ②→④ 被反复调用；每次求解都做守恒自检）", fc="#424242", ec="#424242", fs=15, bold=True, tc="white")
loops = [("run.py", "基准 + 需求±10% + 电价+20%\n+ 工资+5%（5 个场景）\n→ scenario_summary · golden"),
         ("strategies.py", "5 策略：成本优先 / 稳定优先\n(jph_step·shift_quarter·util 0.9·ot 24)\n保人力 head_change 5% / 需求+20%×2"),
         ("strategies.monte_carlo", "固定成本优先/稳定优先的 y\n需求按月 ±8% 抽样 20 次\n→ 平均·P90·缺口概率·延期"),
         ("stress_test.py", "场景库 9 个(旺季/缺芯/限电…)\n焊装 6 月停线 0–10 天扫描\n需求 ×1.0–1.5 找上限"),
         ("run_plant.py / full_cost_compare.py", "任意配置包：检查→求解→回测\nDEMO_B 回测 · 基础 vs 全成本口径")]
for j, (t, dsc) in enumerate(loops):
    box(ax, 0.016 + j*0.195, 0.03, 0.185, 0.115, f"{t}\n{dsc}", fc="white", ec="#424242", fs=14)
xg = 0.3335
ax.plot([xg, xg], [0.185, 0.47], color="#424242", lw=2.4, ls="--")
arrow(ax, (xg, 0.47), (x2+w2, 0.47), color="#424242", ls="--", lw=2.4)
ax.text(xg+0.004, 0.193, "↑ 改旋钮 / 策略约束 / fix_y 后重建模型", fontsize=12.5, color="#424242", bbox=dict(fc="#fafafa", ec="none"))
fig.savefig(OUT, dpi=105); print(OUT)
