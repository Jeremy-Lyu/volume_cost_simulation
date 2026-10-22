"""总体架构图：应用/决策层 → 求解/计算层 → 模型/规则层（实体框架） → 数据层，右侧 AI 增强（示例结构）"""
import os, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import cjkfont; cjkfont.use()

fig = plt.figure(figsize=(26, 18.1)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 26); ax.set_ylim(-0.5, 17.6); ax.axis("off")

def band(y0, y1, fc, ec, title, x0=0.2, x1=19.7):
    ax.add_patch(FancyBboxPatch((x0, y0), x1-x0, y1-y0, boxstyle="round,pad=0.02,rounding_size=0.15", fc=fc, ec=ec, lw=2, zorder=0))
    ax.text(x0+0.18, (y0+y1)/2, title, rotation=90, ha="center", va="center", fontsize=21.1, weight="bold", color=ec, zorder=1)

def box(x, y, w, h, title, body="", fc="white", ec="#455a64", fs=16.5, tfs=18.5, lw=1.4, ls="-", top=False):
    """x,y = 左下角"""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.1", fc=fc, ec=ec, lw=lw, ls=ls, zorder=3))
    if body or top:
        ax.text(x+w/2, y+h-0.12, title, ha="center", va="top", fontsize=tfs, weight="bold", color="#263238", zorder=4)
        ax.text(x+w/2, y+h-0.62, body, ha="center", va="top", fontsize=fs, color="#37474f", zorder=4, linespacing=1.35)
    else:
        ax.text(x+w/2, y+h/2, title, ha="center", va="center", fontsize=tfs, weight="bold", color="#263238", zorder=4)
    return (x, y, w, h)

def arrow(p1, p2, color="#546e7a", lw=2, ls="-", rad=0.0, lab="", lx=None, ly=None, lc=None):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=20, lw=lw, ls=ls, color=color,
                                 connectionstyle=f"arc3,rad={rad}", zorder=5))
    if lab:
        ax.text(lx if lx is not None else (p1[0]+p2[0])/2, ly if ly is not None else (p1[1]+p2[1])/2, lab, fontsize=15.2,
                color=lc or color, ha="center", va="center", zorder=6, bbox=dict(fc="white", ec=lc or color, boxstyle="round,pad=0.25", lw=1))

# ---------- 标题 ----------
ax.text(13, 17.25, "产量成本测算系统（产量成本模拟器）总体架构图", ha="center", fontsize=29.0, weight="bold", color="#263238")
ax.text(13, 16.8, "示例结构，依据《产量成本模型-要素拆解》第 1A、5、9、12–19 节整理；非真实系统设计，标 ⚠ 的需确认", ha="center", fontsize=16.5, color="#607d8b")

# ---------- 层带 ----------
C1, C2, C3, C4 = ("#e8f5e9", "#2e7d32"), ("#fff3e0", "#e65100"), ("#ede7f6", "#4527a0"), ("#e3f2fd", "#1565c0")
band(13.15, 16.45, *C1, "① 应用 / 决策层")
band(9.0, 12.85, *C2, "② 求解 / 计算层")
band(4.85, 8.7, *C3, "③ 模型 / 规则层")
band(0.25, 4.55, *C4, "④ 数据层")

# ---------- ① 应用 / 决策层 ----------
y, h = 13.35, 2.85
box(0.75, y, 3.0, h, "管理层看板 / 报表", "总览 · 趋势 · 方案对比\n单车成本 · 缺口 · 瓶颈车间\n结果注明场景号+参数版本", fs=14.5)
box(3.95, y, 3.65, h, "策略对比（if-then）", "成本优先：总成本最低\n稳定优先：利用率≤90%\n　　少加班、少切换\n保人力：人数月变化≤5%\n保交付：提高缺货惩罚", fs=14.5)
box(7.8, y, 3.45, h, "场景模拟 & 压力测试", "场景库一键运行\n旋钮扫描（如停线 0→10 天）\n组合冲击 · 需求上限\n蒙特卡洛（需求 ±8%）", fs=14.5)
box(11.45, y, 3.6, h, "Laya 类结构化决策模型", "场景识别/路由（choice）\n方案风险把关（noul）\n策略推荐 · 异常分级（score）\n按概率阈值：自动/复核/拦截", fc="#f1f8e9", fs=14.5)
box(15.25, y, 4.25, h, "人工决策（human-in-the-loop）", "管理层在策略之间拍板\nWeb 应用：参数维护 · 发起测算\nLLM 带出处的结果解释\n决策留痕 → 挂到实体框架", fc="#fffde7", ec="#f9a825", lw=2, fs=14.5)

# ---------- ② 求解 / 计算层 ----------
box(0.75, 9.2, 4.3, 3.45, "场景层", "场景旋钮 apply_knobs：\n需求系数 · 开动率系数 · 停线天数\n零件供应上限 · 电价/工资系数\n加班上限\n场景库 scenario_library.csv\n场景ID = 一份冻结的参数快照", fs=15.8)
box(5.3, 9.2, 4.6, 3.45, "子模块：只做计算（固定接口）", "输入：车间 · JPH档 · 班次 · 月\n人力（定员×班次）· 加班费\n能源（固定+变动，电价系数）\n班车 · 外包 · 夜班补贴 · OH\n缓存持有\n→ 方案成本表（预计算）", fs=15.8, fc="#fffaf3")
box(10.15, 9.2, 5.0, 3.45, "主模型：优化求解器（只做选择）", "MIP：PuLP + CBC / HiGHS\n0/1：每车间每月选一个「JPH档×班次」\n连续：加班 0–36h · 缓存 · 产量\n约束：产能 · 需求 · 缓存流平衡 · 供应上限\n目标：总成本 + 缺货惩罚 → 最低\n可选约束：jph_step · shift_quarter\nutil_cap · head_change", fs=14.5, fc="#fff8e1", ec="#e65100", lw=2.2)
box(15.4, 11.0, 4.1, 1.65, "结果库", "plan / cost 明细（场景+方案）\n运营成本 · 缺口 · 单车成本", fs=15.8)
box(15.4, 9.2, 4.1, 1.6, "下层细化模型", "月度方案 → 周度班组 → 日度人员\n不可行时反馈为新约束", fs=15.8)

# ---------- ③ 模型 / 规则层 ----------
box(0.75, 5.05, 5.6, 3.45, "实体框架（Ontology）四层知识", "", fc="#f6f3fc", ec="#4527a0", lw=2, top=True)
for i, (t, b) in enumerate([("定义", "对象\n属性\n取值范围"), ("关系", "对象之间\n关联键"), ("规则", "公式\n约束"), ("依据", "来源文件\n负责人\n生效日期\n适用范围")]):
    box(0.95 + i*1.35, 5.25, 1.22, 2.5, t, b, fc="white", ec="#7e57c2", fs=13.9, tfs=17.2)
box(6.6, 6.85, 6.5, 1.65, "车间链（缓存连接）", "", fc="#f6f3fc", top=True)
shops = ["冲压 STP", "焊装 BIW", "涂装 PNT", "总装 TCF"]
for i, s in enumerate(shops):
    box(6.8 + i*1.6, 7.35, 1.3, 0.62, s, fc="white", ec="#7e57c2", tfs=15.8)
    if i < 3: arrow((6.8+i*1.6+1.33, 7.66), (6.8+(i+1)*1.6-0.03, 7.66), color="#7e57c2", lw=1.8)
ax.text(9.85, 7.22, "每车间：JPH档（按车间离散）→ 定员 · 运行功率 · 产能", ha="center", va="top", fontsize=14.5, color="#4527a0", zorder=4)
box(6.6, 5.05, 3.15, 1.6, "班次模式（离散）", "1班 / 2班 / 3班\n两班12小时 ⚠ 待扩展", fs=15.2, fc="#f6f3fc")
box(9.95, 5.05, 3.15, 1.6, "约束与策略假设", "产能上限 · 加班上限 · 缓存容量\n劳动法规 · 切换约束 · 惩罚", fs=15.2, fc="#f6f3fc")
box(13.35, 5.05, 2.75, 3.45, "参数 & 方法版本", "参数表：车间/车型\n生效日期 · 失效日期\n版本号 · 负责人\n计算方法版本\n（按车间、月份配置）", fs=15.2, fc="#f6f3fc")
box(16.95, 5.05, 2.55, 3.45, "关联键", "车型编码\n车间编码\n月份\nJPH档 · 班次数\n生效日期 · 场景ID", fs=15.8, fc="#f6f3fc")

# ---------- ④ 数据层 ----------
box(0.75, 0.45, 3.4, 3.9, "源系统", "PLM / BOM\nMES / 设备\n人事\n能源计量\n财务\n销售预测 / S&OP", fs=16.5)
box(4.4, 0.45, 3.6, 3.9, "华为云数仓", "ODS 接入\n↓\nDWD 主数据 + 明细\n↓\n参数层（带版本）", fs=16.5, fc="#f3f9ff", ec="#1565c0", lw=2)
box(8.25, 0.45, 7.1, 3.9, "数据域（主数据 / 参数 / 事务）", "", fc="#f3f9ff", top=True)
doms = ["需求 / 订单", "车型配置 & BOM/工时", "日历 / 班次方案", "设备 / 开动率 / OEE",
        "定员标准 / 人员单价", "能源参数 / 电价", "OH / 班车 / 外包费率", "产能上限（产能限制配置）"]
for i, d in enumerate(doms):
    c, r = i % 2, i // 2
    box(8.45 + c*3.45, 2.95 - r*0.62, 3.3, 0.5, d, fc="white", ec="#64b5f6", tfs=15.2)
box(8.45, 0.55, 6.75, 0.5, "实际数据：实际产量 · 实际工时 · 实际能耗 · 实际加班 · 实际成本", fc="#fff", ec="#64b5f6", tfs=15.2)
box(15.6, 0.45, 3.9, 3.9, "数据质量 & 对账校准", "质量规则：空值 · 范围 · 一致性\n（如定员随 JPH 档单调递增）\n测算 vs 实际 逐月对账\n偏差超阈值告警 ⚠\n追溯到参数并修正", fs=15.8, fc="#fff", ec="#1565c0")

# ---------- AI 增强（右侧） ----------
AX0, AX1 = 20.0, 25.8
ax.add_patch(FancyBboxPatch((AX0, 0.25), AX1-AX0, 16.2, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#fce4ec", ec="#ad1457", lw=2, ls="--", zorder=0))
ax.text((AX0+AX1)/2, 16.05, "⑤ AI 增强（旁路，只提建议）", ha="center", fontsize=21.1, weight="bold", color="#ad1457")
box(20.25, 10.3, 5.3, 5.35, "LLM（以实体框架为地图）", "结果解释：沿实体关系、带出处\nRAG 问答：口径 · 参数 · 变更记录\n自然语言场景 → 旋钮草稿\n常识审查：找可疑点\n规则生成：校验项 · 约束初稿\n字段映射建议 · 编码统一\n文档/合同抽取参数候选值\n代码初稿（清洗 · 约束 · 报表）", fs=15.8, fc="#fff", ec="#ad1457")
box(20.25, 4.6, 5.3, 5.45, "ML 场景小模型（提供预测输入）", "需求预测 → demand\n（LightGBM / Prophet；\n候选时序模型 Chronos / TimesFM ⚠）\n开动率 / OEE 预测 → 产能修正\n能耗回归 → 固定 / 单车能耗\n新配置工时估算 → BOM 工时\n文本分类抽取（小语言模型）\n求解代理模型 → 场景筛选", fs=15.8, fc="#fff", ec="#ad1457")
box(20.25, 0.45, 5.3, 3.9, "原则", "LLM 只提建议，人确认后固化\n数字由规则和求解器保证\nLLM 不直接改生产数据\n小模型先基线、再迭代\n月度监控、偏差大就重训\n本地 / 私有云部署，数据不出厂", fs=15.8, fc="#fff", ec="#ad1457")

# ---------- 层间箭头：数据向上（蓝），反馈向下（绿虚线） ----------
UP, DN = "#1565c0", "#2e7d32"
arrow((4.2, 2.4), (4.35, 2.4), color=UP, lw=2.5)
arrow((8.05, 2.4), (8.2, 2.4), color=UP, lw=2.5)
arrow((6.2, 4.4), (6.2, 5.0), color=UP, lw=3, lab="参数快照（场景ID + 生效日期）", lx=8.6, ly=4.7)
arrow((14.85, 4.4), (14.85, 5.0), color=UP, lw=3)
arrow((9.85, 8.55), (9.85, 9.15), color=UP, lw=3, lab="对象 · 关系 · 规则 · 参数", lx=12.0, ly=8.85)
arrow((12.6, 12.7), (12.6, 13.3), color=UP, lw=3, lab="方案 · 成本 · 缺口", lx=14.1, ly=13.0)
arrow((17.45, 12.7), (17.45, 13.3), color=UP, lw=3)
# 层内：场景→子模块→求解器→结果
arrow((5.07, 10.9), (5.28, 10.9), color="#e65100", lw=2.5)
arrow((9.92, 10.9), (10.13, 10.9), color="#e65100", lw=2.5)
arrow((15.17, 11.8), (15.38, 11.8), color="#e65100", lw=2.5)
arrow((15.38, 10.0), (15.17, 10.0), color=DN, lw=2, ls="--")
# 反馈向下
arrow((8.6, 13.3), (3.0, 12.7), color=DN, lw=2.5, ls="--", rad=0.0, lab="选策略 / 新场景 → 旋钮", lx=5.8, ly=13.0, lc=DN)
arrow((16.52, 9.15), (16.52, 4.45), color=DN, lw=2.5, ls="--", lab="偏差\n回写", lx=16.52, ly=6.75, lc=DN)
# AI 旁路箭头
PK = "#ad1457"
arrow((20.2, 14.6), (19.55, 14.6), color=PK, lw=2, ls=(0, (4, 2)), lab="解释", lx=19.85, ly=15.05, lc=PK)
arrow((20.2, 11.0), (19.55, 11.0), color=PK, lw=2, ls=(0, (4, 2)), lab="场景", lx=19.85, ly=11.45, lc=PK)
arrow((20.2, 7.6), (19.55, 7.6), color=PK, lw=2, ls=(0, (4, 2)), lab="规则", lx=19.85, ly=8.05, lc=PK)
arrow((20.2, 5.2), (19.55, 2.8), color=PK, lw=2, ls=(0, (4, 2)), lab="预测\n输入", lx=19.82, ly=3.65, lc=PK)

# ---------- 图例 ----------
ly = -0.38
ax.text(0.3, ly, "图例：", fontsize=15.8, va="bottom", color="#263238", weight="bold")
for x, c, s, t in [(1.3, UP, "-", "数据向上流动"), (4.4, DN, "--", "决策 / 校准反馈向下"), (8.1, "#e65100", "-", "层内计算顺序"), (11.0, PK, (0, (4, 2)), "AI 旁路：建议，需人确认")]:
    ax.plot([x, x+0.7], [ly+0.12, ly+0.12], color=c, lw=2.5, ls=s); ax.text(x+0.8, ly, t, fontsize=15.8, va="bottom", color="#37474f")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "架构图.png")
plt.savefig(out, dpi=100, bbox_inches="tight"); print("ok", out)
