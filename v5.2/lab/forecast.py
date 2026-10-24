"""v5 预测输入：从历史得到需求、开动率的 P10/P50/P90 与抽样
接口 Forecaster.fit(history) / quantiles(q) / sample(n, rng)；当前实现 SeasonalBootstrap（季节因子 + 趋势 + 残差自助抽样）。
后续可替换为 Chronos / TimesFM / LightGBM 分位数回归（ChronosForecaster 为占位，⚠ 未实现）。
无历史文件时 make_history() 生成 36 个月【示例历史】（以示例需求为季节形状 + 随机噪声），文件 data/history_demand.csv、data/history_avail.csv"""
import os as _root_os, sys as _root_sys
_root_sys.path.insert(0, _root_os.path.dirname(_root_os.path.dirname(_root_os.path.abspath(__file__))))
import csv, os, random, statistics as stt
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class Forecaster:
    def fit(self, series): raise NotImplementedError
    def quantiles(self, qs=(0.1, 0.5, 0.9)): raise NotImplementedError
    def sample(self, n, rng): raise NotImplementedError
class SeasonalBootstrap(Forecaster):
    """y[t] = 水平 × 季节因子[month] × 趋势 × (1+残差)；未来 12 个月残差按月份块自助抽样（保留跨月份同年相关性）"""
    def __init__(self, horizon=12, trend=True): self.h, self.trend = horizon, trend
    def fit(self, series):     # series: [(year, month, value)] 按时间排序
        vals = [v for _, _, v in series]; yrs = sorted({y for y, _, _ in series})
        ym = {(y, m): v for y, m, v in series}
        ann = {y: stt.mean(ym[(y, m)] for m in range(1, 13) if (y, m) in ym) for y in yrs}
        self.g = (ann[yrs[-1]] / ann[yrs[0]]) ** (1 / max(len(yrs) - 1, 1)) if self.trend else 1.0
        self.season = {m: stt.mean(ym[(y, m)] / ann[y] for y in yrs if (y, m) in ym) for m in range(1, 13)}
        self.level = ann[yrs[-1]] * self.g
        self.res = {y: {m: ym[(y, m)] / (ann[y] * self.season[m]) - 1 for m in range(1, 13) if (y, m) in ym} for y in yrs}
        self.years = yrs; return self
    def point(self, m): return self.level * self.season[m]
    def sample(self, n, rng):
        out = []
        for _ in range(n):
            y = rng.choice(self.years); r = self.res[y]
            out.append({m: max(self.point(m) * (1 + r.get(m, 0.0) + rng.gauss(0, 0.01)), 0.0) for m in range(1, self.h + 1)})
        return out
    def quantiles(self, qs=(0.1, 0.5, 0.9), n=2000, seed=1):
        s = self.sample(n, random.Random(seed)); res = {}
        for m in range(1, self.h + 1):
            v = sorted(x[m] for x in s); res[m] = {q: v[int(q * (n - 1))] for q in qs}
        return res
class ChronosForecaster(Forecaster):
    """⚠ 占位：接入 amazon/chronos-t5 或 TimesFM 的零样本分位数预测；接口同上"""
    def fit(self, series): raise NotImplementedError("⚠ 仅接口草图：需安装 chronos-forecasting 并接入真实历史")
def make_history(d, years=3, seed=42, path=None):
    """生成【示例历史】：以基准需求为季节形状，年增长 4%，噪声 ±6%；开动率 0.97±0.03（⚠ 示例）"""
    rng = random.Random(seed); path = path or os.path.join(H, "data")
    with open(os.path.join(path, "history_demand.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["year", "month", "model", "demand"])
        for yi in range(years):
            for (t, m), v in sorted(d["demand"].items()):
                w.writerow([2023 + yi, t, m, round(v * 1.04 ** (yi - years) * (1 + rng.gauss(0, 0.06)))])
    with open(os.path.join(path, "history_avail.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["year", "month", "shop", "avail"])
        for yi in range(years):
            for t in range(1, 13):
                for s in d["shops"]: w.writerow([2023 + yi, t, s, round(min(1.0, rng.gauss(0.97, 0.03)), 3)])
def load_history(d, path=None):
    path = path or os.path.join(H, "data"); p = os.path.join(path, "history_demand.csv")
    if not os.path.exists(p): make_history(d, path=path)
    dem, av = {}, {}
    for r in csv.DictReader(open(p, encoding="utf-8")): dem.setdefault(r["model"], []).append((int(r["year"]), int(r["month"]), float(r["demand"])))
    for r in csv.DictReader(open(os.path.join(path, "history_avail.csv"), encoding="utf-8")):
        av.setdefault(r["shop"], []).append((int(r["year"]), int(r["month"]), float(r["avail"])))
    return dem, av
class AvailBootstrap(Forecaster):
    """开动率：按月份的历史值经验分布自助抽样（不外推趋势）"""
    def fit(self, series):
        self.by = {}
        for _, m, v in series: self.by.setdefault(m, []).append(v)
        return self
    def sample(self, n, rng): return [{m: rng.choice(self.by[m]) for m in self.by} for _ in range(n)]
    def quantiles(self, qs=(0.1, 0.5, 0.9)):
        return {m: {q: sorted(v)[int(q * (len(v) - 1))] for q in qs} for m, v in self.by.items()}
def fit_all(d, path=None):
    dem, av = load_history(d, path)
    return ({m: SeasonalBootstrap().fit(sorted(s)) for m, s in dem.items()},
            {s: AvailBootstrap().fit(v) for s, v in av.items()})
def sample_scenarios(d, n, seed=7, path=None):
    """返回 n 个场景：每个 = {"demand": {(t,m):v}, "avail": {(s,t):a}}"""
    fd, fa = fit_all(d, path); rng = random.Random(seed)
    ds = {m: f.sample(n, rng) for m, f in fd.items()}; as_ = {s: f.sample(n, rng) for s, f in fa.items()}
    return [{"demand": {(t, m): ds[m][i][t] for m in fd for t in d["months"]},
             "avail": {(s, t): as_[s][i][t] for s in fa for t in d["months"]}} for i in range(n)]
def quantile_table(d, path=None):
    fd, fa = fit_all(d, path); rows = []
    for m, f in fd.items():
        q = f.quantiles()
        for t in d["months"]: rows.append(dict(对象=m, 类型="需求", 月=t, P10=round(q[t][0.1]), P50=round(q[t][0.5]), P90=round(q[t][0.9]), 计划值=round(d["demand"][(t, m)])))
    for s, f in fa.items():
        q = f.quantiles()
        for t in d["months"]: rows.append(dict(对象=s, 类型="开动率", 月=t, P10=q[t][0.1], P50=q[t][0.5], P90=q[t][0.9], 计划值=1.0))
    return rows
