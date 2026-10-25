"""手册 v4 → v5.2：复制 md/ 到 md_v52/，改过时表述，加第 13 章与附录条目（示例数据）"""
import os, shutil, re, glob
H = os.path.dirname(os.path.abspath(__file__)); B = os.path.dirname(H); S = B + "/md"; T = B + "/md_v52"
shutil.rmtree(T, ignore_errors=True); shutil.copytree(S, T); shutil.copy(H + "/13_v5x.md", T + "/13_v5x.md")
log = []
def rep(f, a, b, cnt=1):
    p = T + "/" + f; s = open(p, encoding="utf-8").read()
    if a not in s: raise SystemExit(f"未找到 {f}: {a[:40]}")
    open(p, "w", encoding="utf-8").write(s.replace(a, b, cnt)); log.append((f, a[:30]))
F = "00_front.md"
rep(F, "凡是 VCS 模拟器（v4）已经实现", "凡是 VCS 模拟器（v4–v5.2）已经实现")
rep(F, "- 代码位置以 **v4 版本**（`review/v4/`）为准：", "- **v5.2 说明**：第 1–12 章的规则与代码位置以 v4 为基础；v5 决策层、v5.1 分时电价/天然气/启停炉/需量/按天排产、v5.2 人工弹性/借调/JPH 换档见**第 13 章**（代码 `review/v5.2/`），第 6 章中已被 v5.1 实现的内容已就地改写。v5.2 的函数名不变，行号以函数名为准。\n- 代码位置以 **v4 版本**（`review/v4/`）为准：")
rep(F, "- **代码**：在 VCS v4 代码里的位置；", "- **代码**：在 VCS v4 代码里的位置（v5–v5.2 新增内容见第 13 章，代码在 `review/v5.2/`）；")
rep(F, "| 14 自查练习 | §12.11 |", "| 14 自查练习 | §12.11 |\n| （新增）v5 决策层、分时电价、天然气、启停炉、按天排产、人工弹性、JPH 换档 | §13 |")
rep(F, "- **要做管理层汇报**：", "- **要看 v5–v5.2 新功能**：§13（每节含公式与示例数据算例）→ `review/v5.2/v5.2升级说明.md`。\n- **要做管理层汇报**：")
F = "05_labor.md"
rep(F, "- **代码**：`shift_options.csv:outsourcing_per_shift_month` → `outsourcing()`（L114）。",
    "- **v5.2**：新增 `labor_flex.csv`（派遣比、停工日发薪%、借调上限），用于计算停工日能省多少人工（§13.7）。⚠ 默认派遣比 20% **超过**《劳务派遣暂行规定》的 10% 上限，只能理解为「派遣 + 临时/短期合同工等可按天调配的人员」合计口径，须 HR/法务确认后再用；严格按派遣口径应 ≤ 10%。\n- **代码**：`shift_options.csv:outsourcing_per_shift_month` → `outsourcing()`（L114）；`cost_functions.flex_var_share()`（v5.2）。")
rep(F, "- **代码**：`ramp.csv` 近似；学习曲线本身未建。", "- **代码**：`ramp.csv` 近似；学习曲线本身未建（v5.2 已登记于 `假设登记表.csv` A06，暂由 JPH 换档损失天数吸收，§13.9）。")
F = "06_energy.md"
rep(F, "- **口径注意**：模拟器只有一个基础电价 × 月度系数（`elec_month_factor`），未分时 ⚠；练习 e3 用\"7、8 月电价 × 1.5\"近似夏季峰电。",
    "- **口径注意**：上面的峰/平/谷价格与时段是**假设示例**。v5.1 起模拟器已按浙江实际分时电价计价（2026 新政高峰 16–23 点，中班最贵、夜班最便宜，与本示例不同），见 §13.2；关闭分时（`tou_enabled=false`）时回到单一电价 × 月度系数（`elec_month_factor`）。")
rep(F, "- **代码**：`cost_functions.price()`（L14–15）；`exercises.e3()`；分时未建（建议 `price[t, 时段]` + 班次时段映射，新方法版本）。",
    "- **代码**：`cost_functions.price(d,t,k)` → `energy.shift_price()`（v5.1）；`tou_periods.csv`、`tou_price.csv`、`shift_times.csv`；`exercises.e3()`。")
rep(F, "  - 模拟器不含基本电费；若加入，应作为常数项或与\"是否开线\"挂钩 ⚠。", "  - v5.1 起模拟器按需量计基本电费：同时率 × 运行功率 × 需量电价（⚠ 0.85、40.8 元/kW·月，`energy_config.json`），见 §13.5。")
rep(F, "- **代码**：未建（建议 `global_params: demand_kw, demand_price`，进入固定常数）。", "- **代码**：`energy.parts()`（月度，科目「需量电费」）；`daily.py`（按天，`peak_kw`）。")
rep(F, "  - 模拟器\"能源\"只建了电，天然气未单列（OEM 费用全集第 7 类\"◐\"）。", "  - v5.1 起天然气已单列为「能源-天然气」：按开炉小时 + 按台 + 保温/电泳保温，见 §13.3。")
rep(F, "- **示例（示例数据，假设值）**：涂装单车用气 12 m³ × 3.5 元/m³ = 42 元/台；保温 + 升温每开线日 1,500 m³ → 18 天 2.7 万 m³ × 3.5 = 9.45 万元/月。",
    "- **示例（示例数据，v5.1 参数 ⚠）**：运行气 450 m³/h、单车吸热 4 m³、气价 3.6 元/m³：JPH30 单车 450 ÷ (30 × 0.9) + 4 = 20.7 m³ → 74.5 元/台；JPH36 为 17.9 m³ → 64.4 元/台。一次启炉 900 m³ + 4,500 kWh ≈ 5,214 元（§13.4）。")
rep(F, "- **代码**：未建（建议 `utility.csv{type, price, per_unit, per_hour, per_startup}`，扩展 `energy_fixed / var_cost_per_unit`）。", "- **代码**：`shop_energy.csv`；`energy.gas / parts / startup_cost`；`cost_functions.var_gas()`（v5.1）。")
rep(F, "  - 模拟器的固定能耗 `run_kw × hours` 已包含开动时段内的空转；**非开动时段的待机能耗未建**，0 班时能耗为 0 会低估成本 ⚠。",
    "  - 模拟器的固定能耗 `run_kw × hours` 已包含开动时段内的空转；v5.1 起非开动时段按 `standby_kw_ratio`（保温）或 `off_kw_ratio + ecoat_hold_kw`（停炉）计待机能耗，周末/夜间按临界间隔自动选择（§13.4）。")
rep(F, "- **代码**：未建（建议 `standby_kw` 字段 × (日历小时 − 开动小时)）。", "- **代码**：`energy.hold_cost_h / off_cost_h / _gap`；科目「能源-电(待机)」（v5.1）。")
rep(F, "price(t) = elec_price × elec_month_factor(t)\n（建议扩展）+ 基本电费 + 天然气 + 待机能耗 + 碳配额购买",
    "price(t) = elec_price × elec_month_factor(t)                    （tou_enabled=false 时）\nprice(t,k) = 班次 k 的分时加权电价（energy.shift_price）        （v5.1 默认）\nv5.1 起另有：能源-电(待机) + 能源-天然气 + 启停能耗 + 需量电费（§13.2–13.5）\nv5.2 起：停工日能源节省（负数，§13.7）")
F = "11_methods.md"
rep(F, "- **代码**：未建（审查 §3.5 建议：固定 y 后 LP 对偶，PuLP 可读 `constraint.pi`）。", "- **代码**：v5 `outputs_v5.shadow_prices()`（月度，有限差分）；v5.1 `daily.py`（固定二进制后读 `bufmax_j` 的 `pi`，白车身库容影子价格）。")
rep(F, "- **代码**：未建（审查 §3.5 建议）。", "- **代码**：v5 `strategy_v5.py`（权重扫描 + no-good cut 生成前三备选）、`outputs_v5.decision_sheet()`。")
F = "91_formulas.md"
rep(F, "| 需量电费 | 月最大需量 kW × 需量电价 | 元 | §6.5 |", """| 需量电费 | 月最大需量 kW × 需量电价（v5.1：同时率 × 运行功率） | 元 | §6.5、§13.5 |
| 班次分时电价 | Σ 该班小时电价 ÷ 小时数 | 元/kWh | `energy.shift_price`；§13.2 |
| 单车用气 | gas_run_m3h ÷ (JPH × 按天产能折算系数) + gas_m3_per_unit | m³/台 | §13.3 |
| 启炉一次 | heatup_kwh × 升温电价 + heatup_m3 × 气价 | 元/次 | `energy.startup_cost`；§13.4 |
| 停炉临界间隔 | 启炉一次 ÷ (保温每小时 − 停炉每小时) | h | `energy.breakeven_hours`；§13.4 |""")
open(T + "/91_formulas.md", "a", encoding="utf-8").write("""

## B.10 v5.2 人工弹性与换档

| 概念 | 公式 | 单位 | 代码 / 章节 |
|:--|:--|:--|:--|
| 停工日可省人工比例 φ | (1−派遣比)(1−正式工发薪%) + 派遣比(1−派遣发薪%) | — | `flex_var_share`；§13.7 |
| 停 1 个工作日省 | 人数 × 月薪 × 福利 ÷ 计薪天数 × φ + 夜班补贴 + 能源差 | 元/天 | `stop_day_saving`；§13.7 |
| 借调上限 | bw ≤ borrow_limit × 车间人数 | 人 | `model_builder`、`daily`；§13.8 |
| JPH 换档 | sw ≥ z_t − z_{t−1}；成本 = 30 万 ⚠ × sw；损失 = 2 天 ⚠ × 日产能 | 元、台 | §13.9 |
| 白车身缓存平衡 | B_j = B_{j−1} + q_BIW − q_PNT，min ≤ B ≤ 库容 | 台 | `daily.build`；§13.6 |
""")
F = "92_disputes.md"
rep(F, "| C20 | 峰谷电价、需量电费、天然气、待机能耗缺失 | 能源成本偏低 | 加入 / 暂不加入 | 先加分时电价与天然气 | 能源管理 | §6.4–6.9 |",
    "| C20 | 峰谷电价、需量电费、天然气、待机能耗 | 能源成本 | — | v5.1 已加入；参数（电压、购电方式、气价、实测能耗、电泳保温）⚠ 待确认 | 能源管理 | §6.4–6.9、§13.2–13.5 |")
open(T + "/92_disputes.md", "a", encoding="utf-8").write("""
| C36 | 派遣/临时工占比、停工日发薪% | 停工日能省多少人工 | 派遣 ≤ 10%（法规）/ 含临时工合计 20% | 20% ⚠ 合计口径；正式工 70%、派遣 0% ⚠ | HR / 法务 | §5.15、§13.7 |
| C37 | 跨车间借调上限与技能匹配 | 少雇人 | 0 / 10% / 更高 | 10% ⚠；月度按人·天总量平衡偏乐观 | 生产部 / HR | §13.8 |
| C38 | JPH 换档成本与损失天数 | 换档频率 | 按历史换档记录 | 30 万元/次 + 2 天 ⚠ | 工艺部 | §13.9 |
| C39 | 夜间是否停炉 | 两班制能源 | 保温 / 停炉 | 保温 ⚠（临界 5.6 h，但兼顾复产质量） | 涂装 / 工艺 | §13.4 |
| C40 | 白车身库容与持有成本 | 开停节奏 | 实际库位数 | 600 台、10 元/台·天 + 资金占用 ⚠ | 物流 / 财务 | §13.6 |
""")
open(T + "/93_params.md", "a", encoding="utf-8").write("""

## D.6 v5.1–v5.2 新增参数表

| 文件 | 字段 | 含义 | 默认（示例数据 ⚠） | 章节 |
|:--|:--|:--|:--|:--|
| energy_config.json | tou_enabled, tou_version, voltage, purchase_mode, demand_charge_kw_month, demand_coincidence, gas_price | 分时电价开关/版本、电压、购电方式、需量电价、同时率、气价 | true、2026、110kV、agent、40.8、0.85、3.6 | §13.2–13.5 |
| tou_periods.csv / tou_price.csv | version, season, hour, period / price_110kV, price_10kV | 时段划分与电价 | 浙江 2026、2024 两版 | §13.2 |
| shift_times.csv | shift, start, end | 班次时刻 | 早 8–16、中 16–24、夜 0–8、加班 8–16 | §13.2 |
| shop_energy.csv | standby_kw_ratio, off_kw_ratio, gas_run_m3h, gas_m3_per_unit, gas_standby_ratio, heatup_kwh, heatup_m3, ecoat_hold_kw, ecoat_hold_m3h, weekend_policy, night_policy | 待机/停炉/燃气/启炉/电泳保温/策略 | 涂装 0.30、0.05、450、4、0.40、4,500、900、150、40、auto、hold | §13.3–13.4 |
| daily_config.json | biw_buffer_max/min/start, pbs_buffer_max, hold_cost_per_unit_day, weekend_ot_multiplier, labor_daily_variable_share, allow_borrow, prev_jph_tier, fix_crew, same_shift_as_crew, dispatch_sweep | 按天排产 | 600/50/200、300、10、2.0、null（按 labor_flex 推出）、true、null | §13.6–13.8 |
| labor_flex.csv | dispatch_share, stopday_pay_regular, stopday_pay_dispatch, borrow_limit, paid_days_month | 人工弹性 | 0.20、0.70、0.00、0.10、21.75 | §13.7–13.8 |
| jph_switch.csv | cost_per_switch, lost_days | JPH 换档 | 300,000 元、2 天 | §13.9 |
| 假设登记表.csv | 假设项、当前取值、影响、责任人、状态 | 待确认事项台账 | 11 项 | §13.10 |
""")
for p in glob.glob(T + "/*.md"):
    s = open(p, encoding="utf-8").read()
    if "吕工" in s or "审阅" in s: print("残留", p)
print("改动", len(log), "处")
p = T + "/12_example.md"; s = open(p, encoding="utf-8").read()
if "v5.2 说明" not in s:
    s = s.replace("\n## 12.0 算例口径与假设", "\n> **v5.2 说明**：本算例沿用 v4 口径（单一电价 0.75、无天然气/待机/需量、无人工弹性与换档成本），用于理解基本计算链；v5.1/v5.2 新口径的算例见 §13.2–13.9。\n\n## 12.0 算例口径与假设", 1)
    open(p, "w", encoding="utf-8").write(s)
rep("07_logistics.md", "流平衡（`model_builder.py:185–187`）；上限（L190）。", "流平衡（`model_builder.py:185–187`）；上限（L190）。v5.1 起另有按天的白车身缓存与 PBS 平衡及库容影子价格（`daily.py`，§13.6）。")
rep("10_kpi.md", "| 单车综合能耗 | Σ 能源 × 折标系数 ÷ 产量 | kgce/台 | ↓ | 月 | 未建（只有电） |", "| 单车综合能耗 | Σ 能源 × 折标系数 ÷ 产量 | kgce/台 | ↓ | 月 | 部分（v5.1 有电、天然气实物量，未折标） |")
print("补充改动完成")
