# 实验室脚本

这些脚本不在默认入口上。命令仍在 `v5.2/` 下执行，例如 `.venv/bin/python lab/run_v5.py`。

| 脚本 | 做什么 |
| :-- | :-- |
| `run_v5.py`、`strategy_v5.py` | 权重扫描。它的「成本优先」和 `run.py` 的精解不要写进同一张决策卡 |
| `stress_test.py` | 场景库、焊装停线扫描、需求上限 |
| `factory_analysis.py` | 一批情景。推到极限默认关 |
| `strategies` 不在这里 | 成本优先、稳定优先、保人力在上一级 `strategies.py` |
| `make_demo_plant.py`、`make_full_cost_plant.py`、`build_margin.py` | 生成另一份配置包 |
| `gen_data.py` | 会覆盖 `data/`。不要运行 |
| `forecast.py`、`risk.py`、`robust.py`、`limits.py`、`outputs_v5.py` | 预测、风险、稳健和决策单，由 `run_v5.py` 调用 |
| `daily_flex_sweep.py`、`daily_buf_bind.py` | 按天开停的扫描 |
| `full_cost_compare.py`、`multiplant.py`、`exercises.py`、`laya_gate.py`、`test_mode_constraints.py` | 对照、多厂、练习和约束检查 |

结果仍写到上一级 `output/`。
