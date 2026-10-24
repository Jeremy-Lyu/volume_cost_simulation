"""业务架构图 v2：业务流程（需求输入→参数维护→测算/模拟→策略决策→执行→实际回收→对账校准）× 角色泳道，编号协作点 C1–C11（示例结构）"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import cjkfont; cjkfont.use()

W, H = 30, 22.8
fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
def rbox(x, y, w, h, fc, ec, lw=1.3, ls="-", z=2, r=0.1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={r}", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
def arrow(p1, p2, color="#546e7a", lw=2.2, ls="-", rad=0.0, z=6, ms=22):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=ms, lw=lw, ls=ls, color=color, connectionstyle=f"arc3,rad={rad}", zorder=z))
def badge(x, y, n, c="#c62828", r=0.27):
    ax.add_patch(Circle((x, y), r, fc=c, ec="white", lw=1.5, zorder=9))
    ax.text(x, y, n, ha="center", va="center", fontsize=12.5, color="white", weight="bold", zorder=10)

ax.text(W/2, H-0.45, "产量成本模拟器 业务架构图 v2：业务流程 × 角色泳道 × 协作点", ha="center", va="top", fontsize=30, weight="bold", color="#263238")
ax.text(W/2, H-1.25, "示例结构，依据《产量成本模型-要素拆解》第 12、14、16–19 节和《AI&Data 组合作建议》RACI 整理；红色编号 = 协作点（详见第 20 节协作点表）；部门分工 ⚠ 待联合确认", ha="center", va="top", fontsize=16, color="#607d8b")

STAGES = ["① 需求输入", "② 参数维护", "③ 测算 / 模拟", "④ 策略决策", "⑤ 执行", "⑥ 实际回收", "⑦ 对账校准"]
SUB = ["销量·订单·车型组合", "口径·版本·负责人", "场景·求解·解释", "策略对比·拍板", "下达·排班·物料", "MES·HR·能源·财务", "偏差·追溯·回写"]
LANES = [("管理层 / 经营决策", "#fffde7", "#f9a825"), ("计划 / 排产（VCS 业务 Owner）", "#e8f5e9", "#2e7d32"),
         ("生产 / 制造工程（IE）", "#f1f8e9", "#558b2f"), ("人事 / HR", "#fff3e0", "#ef6c00"),
         ("能源 / 设施", "#fbe9e7", "#d84315"), ("财务 / 成本", "#ede7f6", "#4527a0"),
         ("物流 / 供应", "#e0f7fa", "#00838f"), ("IT / 数字化", "#eceff1", "#455a64"), ("AI & Data 组", "#e3f2fd", "#1565c0")]
X0, LW, CW = 0.3, 3.5, 3.6     # 泳道标签宽、每列宽
TOP = H - 2.0; HH = 1.35; LH = 1.75
cx = lambda j: X0 + LW + j*CW
# 阶段表头 + 流程箭头
for j, (s, sb) in enumerate(zip(STAGES, SUB)):
    rbox(cx(j)+0.08, TOP-HH, CW-0.36, HH-0.1, "#37474f", "#37474f", z=3)
    ax.text(cx(j)+CW/2-0.1, TOP-0.38, s, ha="center", va="center", fontsize=19, color="white", weight="bold", zorder=4)
    ax.text(cx(j)+CW/2-0.1, TOP-0.95, sb, ha="center", va="center", fontsize=13.5, color="#cfd8dc", zorder=4)
    if j < 6: arrow((cx(j)+CW-0.27, TOP-HH/2-0.05), (cx(j+1)+0.07, TOP-HH/2-0.05), color="#37474f", lw=2.5)
ax.text(X0+LW/2, TOP-HH/2, "角色 \\ 流程", ha="center", va="center", fontsize=17, weight="bold", color="#263238")
# 泳道
Y = lambda i: TOP - HH - 0.12 - (i+1)*LH
for i, (n, fc, ec) in enumerate(LANES):
    rbox(X0, Y(i)+0.04, LW + 7*CW - 0.2, LH-0.08, fc, ec, lw=1.6 if i != 8 else 2.6, z=0)
    ax.text(X0+0.15, Y(i)+LH/2, n, ha="left", va="center", fontsize=15.5, weight="bold", color=ec, zorder=4)
# 单元格内容：(泳道, 阶段) -> (文字, [协作点])
CELL = {
 (0,0): ("经营目标 · 销量目标", []), (0,3): ("在策略之间拍板\n确认风险接受度", ["C6"]), (0,6): ("审阅月度偏差简报", []),
 (1,0): ("S&OP 需求 · 车型组合", ["C3"]), (1,1): ("产能上限 · 日历", ["C1"]), (1,2): ("定义场景 · 发起测算\n确认业务规则", ["C3","C4"]),
 (1,3): ("方案对比 · 提报", ["C5"]), (1,4): ("下达月度计划", ["C7"]), (1,6): ("确认校准方案", ["C9"]),
 (2,1): ("工时 · JPH 档 · 定员标准", ["C1"]), (2,2): ("工艺约束 · 瓶颈确认", ["C4"]), (2,4): ("周 / 日排产 · 班组\n不可行→反馈约束", ["C7"]),
 (2,5): ("MES 产量 · 开动率 · 停线", ["C8"]), (2,6): ("解释工艺类偏差", ["C9"]),
 (3,1): ("工资 · 加班 · 夜班补贴\n出勤 · 劳动规则", ["C1"]), (3,4): ("调配 · 招聘 · 排班", ["C7"]), (3,5): ("实际工时 · 加班", ["C8"]),
 (4,1): ("电价 · 功率 · 单车能耗", ["C1"]), (4,5): ("计量能耗", ["C8"]), (4,6): ("解释能耗偏差", []),
 (5,0): ("预算 · 成本口径", []), (5,1): ("OH · 班车 · 外包单价\n成本科目口径", ["C1"]), (5,3): ("认可成本口径\n节约额口径", ["C6"]),
 (5,5): ("实际成本（按科目）", ["C8"]), (5,6): ("对账签认", ["C9"]),
 (6,0): ("供应能力 · 船期", ["C3"]), (6,1): ("缓存容量 · 物流费率", ["C1"]), (6,4): ("物料 / 物流配合", []), (6,5): ("缺料 · 到货实际", ["C8"]),
 (7,1): ("源系统接口 · 权限", ["C2"]), (7,2): ("平台运行 · 调度", []), (7,5): ("数据抽取 · 接口运维", ["C2"]),
 (8,0): ("需求预测小模型", ["C10"]), (8,1): ("参数表 · 版本 · 质量规则\n实体框架 · 数据标准", ["C1","C2"]),
 (8,2): ("求解器 · 场景库 · 旋钮\nLLM 解释 · 自然语言场景", ["C4","C5"]), (8,3): ("策略对比视图\nLaya 风险把关 · 推荐", ["C5","C6"]),
 (8,4): ("下层排班接口", []), (8,5): ("数仓入湖 · 质量检查", ["C2","C8"]), (8,6): ("偏差报告 · 校准建议\n异常分级", ["C9"]),
}
for (i, j), (t, bs) in CELL.items():
    x, y = cx(j)+0.12, Y(i)+0.17
    rbox(x, y, CW-0.44, LH-0.34, "white", LANES[i][2], lw=1.2, z=3)
    ax.text(x+(CW-0.44)/2, y+0.58, t, ha="center", va="center", fontsize=13.5, color="#263238", zorder=4, linespacing=1.3)
    for k, b in enumerate(bs): badge(x+CW-0.72-(len(bs)-1-k)*0.56, y+LH-0.6, b, r=0.22)
# 循环：⑦ → ②（校准回写参数）
yb = Y(8) - 0.5
YA = Y(8) - 0.3
ax.plot([cx(6)+CW/2]*2, [Y(8)+0.17, YA], color="#2e7d32", lw=3, ls="--")
arrow((cx(6)+CW/2, YA), (cx(1)+CW/2, YA), color="#2e7d32", lw=3, ls="--")
ax.plot([cx(1)+CW/2]*2, [YA, YA], color="#2e7d32")
arrow((cx(1)+CW/2, YA), (cx(1)+CW/2, Y(8)+0.15), color="#2e7d32", lw=3, ls="--")
ax.text((cx(1)+cx(6))/2+CW/2, YA-0.15, "闭环：对账偏差 → 参数校准（新版本，带生效日期）→ 下一轮测算", ha="center", va="top", fontsize=15, color="#2e7d32", weight="bold",
        bbox=dict(fc="white", ec="#2e7d32", boxstyle="round,pad=0.3"), zorder=7)
# 跨阶段协作点（底部）
yb = Y(8) - 3.25; hb = 1.95
items = [("C10", "小模型开发与上线", "AI&Data 组 R/A；业务提问题和历史数据\n回测优于基线才上线；业务有否决权 · 月度监控重训", "#6a1b9a"),
         ("C11", "推广复制（多工厂）", "中心团队 + 工厂 key user；核心标准不改\n工厂配置包 + 上线六步 + 波次推广（第 21 节）", "#00695c"),
         ("C12", "治理节奏", "双周例会 · 月度管理层简报 · 参数变更审批\n模型上线评审 · 阶段评审（⚠ 频率待定）", "#37474f")]
wb = (LW + 7*CW - 0.2 - 0.4) / 3
for k, (n, t, b, c) in enumerate(items):
    x = X0 + k*(wb+0.2)
    rbox(x, yb, wb, hb, "white", c, lw=2, z=3)
    badge(x+0.45, yb+hb-0.42, n, c=c, r=0.34)
    ax.text(x+0.95, yb+hb-0.42, t, ha="left", va="center", fontsize=17, weight="bold", color=c, zorder=4)
    ax.text(x+wb/2, yb+hb-0.85, b, ha="center", va="top", fontsize=14, color="#37474f", zorder=4, linespacing=1.4)
# 协作点图例（编号-名称）
CP = ["C1 参数口径与归属", "C2 数据接入与质量", "C3 需求与场景定义", "C4 模型逻辑变更", "C5 测算发布与解释", "C6 策略决策与留痕",
      "C7 执行下达与下层反馈", "C8 实际数据回收", "C9 月度对账校准", "C10 小模型开发", "C11 推广复制", "C12 治理节奏"]
ly = yb - 0.55
ax.text(X0, ly, "协作点：", fontsize=15, weight="bold", color="#c62828", va="center")
for k, s in enumerate(CP):
    ax.text(X0 + 1.4 + (k % 6)*4.35, ly - (k//6)*0.5, s, fontsize=14.5, color="#37474f", va="center")
ax.text(X0, ly-1.15, "原则：成果归业务 · 参数谁产生谁负责 · AI 只提建议、数字由规则和求解器保证 · 所有结果注明场景号和参数版本 · 决策留痕挂到实体框架", fontsize=14.5, color="#455a64", va="center")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "业务架构图.png")
plt.savefig(out, dpi=90, bbox_inches="tight", pad_inches=0.2); print("ok", out)
