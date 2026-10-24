"""v4 业务架构图：角色泳道 × 月度运作流程 × 输出与决策（依据 v4 实际文件，示例数据）"""
import os, sys; sys.path.insert(0, os.path.dirname(__file__))
from common import *
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "..", "发布", "版本记录", "v4业务架构图.png")
fig = plt.figure(figsize=(34, 21)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
ax.text(0.5, 0.975, "VCS 产量成本模拟器 v4 · 业务架构图（角色泳道 × 月度运作 × 输出与决策）", ha="center", fontsize=26, fontweight="bold")
ax.text(0.5, 0.952, "依据 v4 实际代码与配置包 data/*.csv、output/*.csv ｜ 全部为示例数据 ｜ ⚠ = 暂定参数待业务确认 ｜ R1–R7 = 吕工确认的 7 条业务规则",
        ha="center", fontsize=14, color="#555")
steps = ["① 参数更新", "② plant_check\n就绪检查", "③ 跑基准\nrun.py / run_plant.py", "④ 场景 / 策略\nstress_test / strategies",
         "⑤ 决策单\n审批", "⑥ 执行", "⑦ 实际回收", "⑧ 对账校准"]
roles = [("计划", "#e3f2fd"), ("IE / 制造工程", "#e8f5e9"), ("HR", "#fff3e0"), ("能源 / 设施", "#fffde7"), ("财务", "#fce4ec"),
         ("生产", "#ede7f6"), ("计划员\n(模拟器用户)", "#e0f7fa"), ("管理层", "#efebe9"), ("AI & Data 组", "#f1f8e9")]
X0, LW, RX = 0.01, 0.075, 0.80          # 角色列宽 / 输出列起点
SW = (RX - X0 - LW - 0.005) / len(steps)
TOP, BOT = 0.862, 0.035; HT = 0.905; RH = (TOP - BOT) / len(roles)
cx = lambda j: X0 + LW + 0.005 + j*SW
ry = lambda i: TOP - (i+1)*RH
for j, s in enumerate(steps):
    box(ax, cx(j)+0.002, HT, SW-0.004, 0.042, s, fc="#37474f", ec="#37474f", fs=12.5, bold=True, tc="white")
box(ax, RX+0.004, HT, 1-RX-0.012, 0.042, "收到的输出 → 支持的决策", fc="#b71c1c", ec="#b71c1c", fs=13, bold=True, tc="white")
for i, (r, c) in enumerate(roles):
    ax.add_patch(plt.Rectangle((X0, ry(i)), 1-X0-0.008, RH, fc=c, ec="#90a4ae", lw=1))
    ax.text(X0+LW/2, ry(i)+RH/2, r, ha="center", va="center", fontsize=15, fontweight="bold")
    ax.plot([X0+LW, X0+LW], [ry(i), ry(i)+RH], color="#90a4ae", lw=1)
ax.plot([RX, RX], [BOT, TOP], color="#b71c1c", lw=2)
def cell(i, j, t, fc="#ffffff", ec="#455a64", fs=13, span=1):
    box(ax, cx(j)+0.003, ry(i)+0.006, SW*span-0.006, RH-0.012, t, fc=fc, ec=ec, fs=fs)
def outc(i, t, fs=13):
    box(ax, RX+0.005, ry(i)+0.006, 1-RX-0.014, RH-0.012, t, fc="#fff8f8", ec="#b71c1c", fs=fs, ha="left")
# ① 参数提供（实际 CSV）
cell(0, 0, "demand.csv 需求\ncalendar.csv 工作日\ncapacity_limit.csv\n车型产能上限")
cell(1, 0, "jph_options.csv\nJPH档/每班定员/kW\nshift_options.csv\n班制·night_shifts⚠(R6)")
cell(2, 0, "global_params.csv\nwage · std_hours⚠\not_multiplier 1.5⚠(R5)\n夜班30元⚠(R6)·上限60h⚠(R4)", fs=12.5)
cell(3, 0, "global: elec_price\njph_options: run_kw\nshop_params:\nkwh_per_unit")
cell(4, 0, "shop_params: OH固定/变动\nhold_cost·idle_fixed⚠(R3)\nshift_options: 班车/外包\nglobal: 延期1500⚠(R2)", fs=12.5)
cell(5, 0, "shop_params:\not_max 36h/人(R4)\nbuffer_cap 车间总量(R1)\n停线/开动率→场景旋钮")
cell(8, 0, "data_source_map.csv\n参数→源系统→负责人\n质量规则/接入")
# ② ~ ⑤ 计划员主流程
cell(6, 1, "plant_check.py\n结构/完整性/规则\n→ readiness_<厂>.md\n(L0–L3 就绪度)")
cell(8, 1, "规则失败→退回\n参数负责人修正", fc="#f9fbe7")
cell(6, 2, "run.py 基准+4场景\n每次求解自动:\n守恒自检 selfcheck\n+ golden 比对")
cell(6, 3, "stress_test.py 场景库\nstrategies.py 策略+\n蒙特卡洛\nscenario_library.csv")
cell(0, 3, "提需求波动/\n旺季/缺芯场景", fc="#f5f5f5")
cell(6, 4, "填 decision_log_\ntemplate.csv\n方案·理由·风险")
cell(7, 4, "审批决策单\n选策略: 成本优先/\n稳定优先/保人力", fc="#fff3e0", ec="#e65100")
# ⑥ 执行 ⑦ 回收
cell(0, 5, "按 plan 排产\n延期订单沟通(R2)")
cell(5, 5, "按 JPH×班次开线\n加班/停线(R3)执行")
cell(2, 5, "加班审批/排班\n招聘或调岗")
cell(5, 6, "actual.csv\n实际产量(车间×月)")
cell(4, 6, "月结实际成本\n(⚠ 原型未接入)", fc="#f5f5f5")
cell(2, 6, "实际人数/加班\n(⚠ 原型未接入)", fc="#f5f5f5")
# ⑧ 对账
cell(8, 7, "run_plant.py 回测\nplant_<厂>_backtest.csv\n偏差 ±5%⚠ 超阈→\n归因到参数")
cell(4, 7, "成本口径对账\naccount_map.csv")
cell(1, 7, "定员/JPH档\n修正")
# 输出 → 决策
outc(0, "scenario_summary.csv：产量/延期台月/流失台\n→ 排产与延期交付(R2)；S&OP 能力承诺")
outc(1, "plan_<场景>.csv：jph · shifts · util\n→ JPH/班次切换；瓶颈车间；提档投资")
outc(2, "plan：heads/total_heads · ot_per_head ·\not_excess_hours → 加班审批(R4)、招聘/人力")
outc(3, "cost_<场景>.csv：能源固定 / 能源变动\n→ 能源预算；限电·峰谷场景")
outc(4, "cost_*.csv 各科目 + account_map.csv\n→ 制造成本预算；单车成本(运营成本/产量)")
outc(5, "plan：shifts=0 · buffer_end · util\n→ 停线(0班, R3)；缓存与库位(R1)")
outc(6, "readiness_*.md · results_summary.md\n→ 能否出正式测算；场景对比")
outc(7, "strategy_summary · montecarlo_summary\n→ 成本 vs 稳定 vs 保人力取舍；风险(P90)")
outc(8, "backtest 偏差 · golden 比对结果\n→ 模型可信度；参数回写与版本")
# 主流程箭头（计划员泳道）
yy = ry(6) + RH/2
for j in range(1, 4): arrow(ax, (cx(j)+SW-0.003, yy), (cx(j+1)+0.003, yy), lw=2.6)
arrow(ax, (cx(4)+SW/2, ry(6)+RH-0.006), (cx(4)+SW/2, ry(7)+0.006+RH-0.012), color="#e65100", lw=2.6)   # 决策单→管理层（向下）
xb = cx(1) + SW*0.3   # 参数汇总母线 → plant_check
for i in (0, 1, 2, 3, 4, 5): ax.plot([cx(0)+SW-0.003, xb], [ry(i)+RH/2]*2, color="#78909c", lw=1.6)
arrow(ax, (xb, ry(0)+RH/2), (xb, ry(6)+RH-0.006), color="#78909c", lw=1.8, ms=16)
ax.text(xb+0.004, ry(3)+RH/2, "各部门参数\n汇入检查", fontsize=12, color="#546e7a", va="center")
arrow(ax, (cx(1)+SW/2, ry(6)+0.006), (cx(1)+SW/2, ry(8)+RH-0.006), color="#827717", lw=1.8)
arrow(ax, (cx(4)+SW-0.003, ry(7)+RH/2), (cx(5)+0.003, ry(5)+RH/2), color="#e65100", lw=2.2)
arrow(ax, (cx(4)+SW-0.003, ry(7)+RH/2), (cx(5)+0.003, ry(2)+RH/2), color="#e65100", lw=1.6)
arrow(ax, (cx(4)+SW-0.003, ry(7)+RH/2), (cx(5)+0.003, ry(0)+RH/2), color="#e65100", lw=1.6)
arrow(ax, (cx(5)+SW-0.003, ry(5)+RH/2), (cx(6)+0.003, ry(5)+RH/2), lw=2.2)
arrow(ax, (cx(6)+SW-0.003, ry(5)+RH/2), (cx(7)+0.004, ry(8)+RH/2), lw=2.2)
arrow(ax, (cx(7)+SW/2, ry(8)+RH-0.006), (cx(7)+SW/2, ry(4)+0.006), color="#2e7d32", ls="--", lw=1.8)
arrow(ax, (cx(7)+SW/2, ry(4)+RH-0.006), (cx(7)+SW/2, ry(1)+0.006), color="#2e7d32", ls="--", lw=1.8)
# 校准回写 ⑧ → ①（绿色虚线，走表头与泳道之间的通道）
yc = (TOP + HT) / 2
ax.plot([cx(7)+SW*0.5, cx(7)+SW*0.5], [ry(1)+RH-0.006, yc], color="#2e7d32", lw=2.4, ls="--")
ax.plot([cx(7)+SW*0.5, cx(0)+SW*0.5], [yc, yc], color="#2e7d32", lw=2.4, ls="--")
arrow(ax, (cx(0)+SW*0.5, yc), (cx(0)+SW*0.5, ry(0)+RH-0.005), color="#2e7d32", ls="--", lw=2.4)
ax.text(cx(4), yc, " ⑧→① 对账偏差 → 参数回写（新版本 + 生效日期），下月重跑 ", fontsize=13, color="#2e7d32", ha="center", va="center",
        bbox=dict(fc="white", ec="#2e7d32", boxstyle="round,pad=0.3"))
# 图例
ax.text(0.01, 0.012, "图例：蓝色实线 = 月度主流程 ｜ 灰色 = 参数汇入检查 ｜ 橙色 = 决策下达 ｜ 绿色虚线 = 对账校准反馈 ｜ 灰底框 = 原型尚未接入的环节 ｜ "
        "R1 缓存=车间总量 R2 缺口可延期 R3 允许0班 R4 加班36h/人可突破 R5 加班价=时薪×倍数 R6 两班有夜班补贴 R7 间接人工归人工",
        fontsize=12, color="#333")
fig.savefig(OUT, dpi=110); print(OUT)
