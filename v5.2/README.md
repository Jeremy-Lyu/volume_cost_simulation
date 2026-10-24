# 产量成本模拟（v5.2）

示例数据，配置包 `TZ-cfg-2026.10-示例`。数字不能当成工厂实绩。

读代码之前，先读 [发布/案例解析.md](../发布/案例解析.md)。那一篇用「9–12 月需求涨 15%」和「电价涨两成」走完：旋钮改了什么、班次怎么变、钱差在哪几个科目、哪些结论还不能对外说。文档都在仓库的 [发布/](../发布/)。历史 Word、结构图和对照表在 `发布/版本记录/`。求解结果在 `output/`，运行日志在 `output/logs/`。代码留在本目录，命令从这里执行。

改工资、需求、班次、策略或公式，按 [修改流程说明](../发布/修改流程说明.md)。字段和核对项在 [工厂改数与重算指南](../发布/工厂改数与重算指南.md)。不要运行 `gen_data.py`：它会覆盖 `data/` 里已有的表，并写成更早的列。

## 运行

命令都在本目录执行。解释器用 `.venv`（已装 PuLP 2.9）。系统自带的 Python 没有求解器。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python plant_check.py          # 先检查 data/ 的结构和规则
.venv/bin/python run.py                  # 基准 + 需求±10% + 电价+20% + 工资+5%
.venv/bin/python -m workbench.api --scenario 旺季冲量
.venv/bin/streamlit run workbench/app.py --server.headless true --server.port 8501
```
演示样例（不必先求解）在 [发布/样例/](../发布/样例/)。

网页打开后有五页：选场景、滑块、对比与决策卡、参数来源、对话。对话只把中文译成旋钮，确认之后才求解。

`run.py` 的时限在 `data/global_params.csv` 的 `solver_time_limit`（示例 120 秒），五个场景通常要数分钟。改完表之后的快速重算是 `run_quick.py`（按文件哈希只跑受影响的层）。策略对比是 `strategies.py`，预置压力场景是 `factory_analysis.py`。

## 结果放哪

| 文件 | 内容 |
| :-- | :-- |
| `output/results_summary.md` | 五个标准场景的总成本和班次 |
| `output/plan_<场景>.csv` | 每车间每月 JPH、班次、人数、加班、产量 |
| `output/cost_<场景>.csv` | 成本分项 |
| `output/workbench/*.md` | 网页或命令行写出的决策卡 |
| `output/strategy_summary.csv` | 成本优先 / 稳定优先 / 保人力 |

决策卡上的「运营成本」和 `run.py` 表上的「总成本」取整可能差一两万。案例解析文首写了怎么对。策略卡的对照是扫描口径里的成本优先，场景卡的对照是基准，两张卡的差额不要加在一起。

## 模块

| 文件 | 做什么 |
| :-- | :-- |
| `data/*.csv`、`plant.json` | 主数据、需求、产能、JPH、班次、工厂配置包 |
| `data_loader.py` | 读表、校验、场景覆盖 |
| `scenarios.py` | 旋钮 `apply_knobs`，读取 `scenario_library.csv` |
| `cost_functions.py` | 人力、加班、能源接口、制造费用 |
| `energy.py` | 浙江分时电价、运行/待机/天然气/启停/需量 |
| `model_builder.py` | 月度 MILP |
| `daily.py` | 焊装 → 白车身缓存 → 涂装，按天 |
| `report.py` | 报表科目、自检 |
| `run.py` | 五个标准场景，并和 `golden.csv` 比对 |
| `workbench/` | 决策卡、网页、中文对话 |
| `strategies.py` | 三种策略和蒙特卡洛 |
| `stress_test.py` | 场景库、焊装停线扫描 |
| `plant_check.py`、`run_plant.py` | 换配置包检查并求解 |
| `weekly.py` | 周序列。默认不改月模型，`--apply` 才回写并重解一次 |

能源分项的参数表在 `data/tou_*.csv`、`shift_times.csv`、`shop_energy.csv`、`energy_config.json`。按天参数在 `data/daily_config.json`。尚未确认的假设在 `data/假设登记表.md`。

## 全成本口径（可选）

缺文件就不启用，和基础口径逐位一致。

```bash
.venv/bin/python make_full_cost_plant.py
.venv/bin/python plant_check.py plants/FULL_COST
.venv/bin/python full_cost_compare.py
```

物料只进报表。配了 `margin.csv` 之后，目标改为成本减去边际贡献。其余可选表（间接定员、FTT、爬坡、换型、发运、模具、折旧）见 [工厂改数与重算指南](../发布/工厂改数与重算指南.md) 第 2.4 节。

## 往场景库加一行

在 `data/scenario_library.csv` 加一行，`knobs` 用 JSON。CSV 里整段用双引号包住，内部双引号写两次。可用旋钮写在 `scenarios.py` 文件头。网页「选场景」和 `python -m workbench.api --scenario 名字` 都读这张表。
