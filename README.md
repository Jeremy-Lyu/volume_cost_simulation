# 产量成本模拟（Volume Cost Simulation）

车间每月在 JPH 档 × 班次里选一个组合，再算人工、能源、加班和制造费用，用来回答：**需求、电价、停线或加人速度变了以后，班次怎么改、钱差在哪几个科目。**

全部数字是示例。配置包代号 `TZ-cfg-2026.10-示例`。不能当成工厂实绩，也不能写成已经省下的钱。

个人示例项目，许可证见 [LICENSE](LICENSE)（MIT）。声明见 [NOTICE.md](NOTICE.md)。

## 仓库里有什么

| 路径 | 内容 |
| :-- | :-- |
| [v5.2/](v5.2/) | 现行代码、示例配置包、工作台 |
| [DOC/](DOC/) | 项目总览、改数指南、发布稿 |
| [samples/](samples/) | 一份可提交的基准汇总和决策卡样例 |
| [NOTICE.md](NOTICE.md) | 示例数据声明、许可证待定、不宜公开的内容 |
| `archive/`（本机） | 旧版代码，已在 `.gitignore`，不进远程仓库 |

先读 [v5.2/docs/案例解析.md](v5.2/docs/案例解析.md)，再改自己的表。

## 快速开始

```bash
cd v5.2
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python plant_check.py
.venv/bin/python run.py
.venv/bin/python -m workbench.api --scenario 旺季冲量
.venv/bin/streamlit run workbench/app.py --server.headless true --server.port 8501
```

不要运行 `gen_data.py`：它会覆盖已填写的表。

## 读结果时

- 决策卡上的「运营成本」和 `run.py` 的「总成本」取整可能差一两万。
- 借调净额达到阈值时会标**未验证**。按天核对之前不要当成节约。
- 六个粗参数在 `data/coarse_params.csv`，默认不改变现成本。场景「开停校正」才打开示例值。

## 发布前

见 [docs/发布准备.md](docs/发布准备.md)。第一版建议私有仓库；选定许可证并确认没有专有背景稿之后，再考虑公开。
