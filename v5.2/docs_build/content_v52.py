"""图表汇编 v5.2：在 v5.1 图目录上只改受影响的图（图 9 基准、v5 决策层、图 10–11 按 v5.2 重算），新增 v5.2 三张图。数字读 v5.2 输出（示例数据）"""
import csv, sys
sys.path.insert(0, '/workspace/review/v5.2/docs_build')
import content_v51 as c1
V = '/workspace/review/v5.2/output'
D = '《产量成本模型-要素拆解-v5.2.md》'; U = '《v5.2升级说明.md》'
rd = lambda p: list(csv.DictReader(open(p, encoding='utf-8-sig')))
sm = {r['场景']: r for r in rd(V + '/scenario_summary.csv')}; b = sm['基准']
dm = open(V + '/v5/管理层决策单.md', encoding='utf-8').read()
con = next(x for x in dm.split('\n') if x.startswith('**结论**')).replace('**结论**：', '')
risk = [x[2:] for x in dm.split('\n') if x.startswith('- ') and 'P(成本超预算)' in x]
cost = {r['科目']: float(r['金额_元']) for r in rd(V + '/cost_基准.csv')}
tot = sum(v for k, v in cost.items() if v > 0)
st = {r['策略']: r for r in rd(V + '/strategy_summary.csv')}
lib = {r['场景']: r for r in rd(V + '/stress_library.csv')}
cl = rd(V + '/stress_demand_ceiling.csv')
first = next((r for r in cl if float(r['流失']) > 0), None)
FIGS = []
for f in c1.FIGS:
    f = list(f)
    if f[1] == '基准结果demo.png':
        f[3] = '基准结果demo.png（v5.2/plot_demo.py 按 v5.2 结果重新生成）'; f[4] = D + ' 第 31.2 节'
        f[6] = (f'v5.2 基准年总成本 {int(b["总成本_万元"]):,} 万元，单车 {int(b["单车成本_元"]):,} 元（v5.1 为 44,746 万），延期 {b["延期台月"]} 台·月。'
                f'人工 {cost["人工"]/1e4:,.0f} 万，停工日人工节省 {cost.get("停工日人工节省",0)/1e4:,.0f} 万、借调节省 {cost.get("借调节省人工",0)/1e4:,.0f} 万（⚠ 月度借调偏乐观），JPH 换档 {cost.get("JPH换档",0)/1e4:,.0f} 万。')
        f[7] = '饼图只画正数科目；节省类科目（负数）见 v5.2/output/cost_基准.csv。'
    elif f[1] == '策略对比.png':
        f[2] = '策略对比（v5.2 重算）'; f[3] = 'v5.2/output/策略对比.png（strategies.py + plot_strategy.py，v5.2 重算）'
        a, s_, h = st['成本优先'], st['稳定优先'], st['保人力(人数月变化≤5%)']
        f[6] = (f'成本优先 {int(a["总成本_万元"]):,} 万 / {a["单车_元"]} 元，延期 {a["延期台月"]}；保人力 {int(h["总成本_万元"]):,} 万（+{int(h["总成本_万元"])-int(a["总成本_万元"])} 万），人数波动 {h["最大人数月波动"]}；'
                f'稳定优先 {int(s_["总成本_万元"]):,} 万，利用率 {s_["平均利用率"]}。需求 +20% 时两种惩罚的总成本相同（50,867 万），保交付不流失。')
        f[7] = '利用率按毛产能（含停工日与换档损失）计算；v5.1 汇编中的本图是 v5 结果，现已替换。'
    elif f[1] == '压力测试.png':
        f[3] = 'v5.2/output/压力测试.png（stress_test.py + plot_stress.py，v5.2 重算）'
        z = lib.get('组合冲击', {})
        f[6] = (f'基准 {int(lib["基准"]["运营成本_万元"]):,} 万；旺季冲量 {int(lib["旺季冲量"]["运营成本_万元"]):,} 万；组合冲击 {int(float(z.get("运营成本_万元",0))):,} 万、流失 {z.get("流失","-")} 台、瓶颈 {z.get("瓶颈车间","-")}。'
                + (f'需求系数 {first["需求系数"]} 起开始流失。' if first else ''))
        f[7] = 'v5.1 汇编中的本图是 v5 结果，现已替换；加班小时轴改为自动刻度。'
    elif f[0] == '三、v5 决策层':
        f[3] = f[3].replace('v5.1/output/v5/', 'v5.2/output/v5/').replace('v5.1 全流程', 'v5.2 全流程')
        if f[1] == '帕累托前沿.png': f[6] = '推荐与理由：' + con
        elif f[1] == '成本分布_风险.png': f[6] = '；'.join(risk) + '。'
        elif f[1] == '成本瀑布_成本优先_vs_推荐.png': f[6] = '起点为扫描口径的成本优先，终点为推荐方案。' + con.split('；')[0]
        elif f[1] == '管理层决策单.png': f[6] = '决策单、瀑布、结论用同一基准。' + con.split('；')[0]
        if f[7].startswith('⚠ 示例数据；扫描用'): f[7] = '⚠ 示例数据；扫描用 gap 0.2%。v5.2 成本优先扫描口径 44,297 万元，精解 44,288 万元。'
    elif f[0].startswith('五、v5.1'):
        f[7] = (f[7] + ' 本图为 v5.1 结果（未含人工弹性），v5.2 的按天结果见图 29。').strip()
    FIGS.append(tuple(f))
P = '六、v5.2 人工弹性与换档'
FIGS += [
 (P, '图7_v51_v52科目变化.png', '月度基准：v5.1 → v5.2 按科目变化', 'v5.2/output/v5.2/图7_v51_v52科目变化.png（plot_v52.py）', D + ' 31.2；' + U + ' 第 2 节',
  '每根横条是一个科目 v5.2 减 v5.1 的差（万元/年），绿色是减少，红色是增加。',
  '合计 44,746 → 44,288 万元（−458）。最大的两项是借调节省 −1,437 万与借出方占用 +604 万（净 −833），停工日人工 −777 万、能源 −356 万；人工 +1,982 万是因为换档少了、全年用更高的档。',
  '⚠ 月度借调只按人·天总量平衡，偏乐观；按天模型逐日核对后借调为 0。'),
 (P, '图8_JPH换档轨迹.png', 'JPH 档月度轨迹：v5.1 vs v5.2', 'v5.2/output/v5.2/图8_JPH换档轨迹.png', D + ' 31.2',
  '四个车间各一张图，灰色粗线是 v5.1，蓝色细线是 v5.2，图例里是全年换档次数。',
  '加入换档成本（30 万元/次 + 2 天产出 ⚠）后，全年换档从 18 次降到 1 次（焊装 9 月 30 → 36）。',
  '⚠ 第一个月不计换档；从 0 班恢复也算一次。'),
 (P, '图9_派遣比敏感性.png', '派遣比敏感性：开几天停几天值不值、库容何时卡住', 'v5.2/output/v5.2/图9_派遣比敏感性.png（daily_flex_sweep.py、daily_buf_bind.py）', D + ' 31.4；' + U + ' 第 4 节',
  '左图：月需求 6,000 台、2 班定员，蓝色 = 每天可少开一班，红色 = 只能整班开/整天停；实线 = 模型自主，虚线 = 每个工作日都开。右图：整班口径、派遣 50% 时库容 100–600 台的成本与影子价格。',
  '能少开班时，停整天没有收益（差距在求解精度内）；只能整班开时，停 3 天（开 19/22 天）省 38.6 / 47.4 / 62.1 万元/月（派遣 0/20/50%）。库容 100–600 台影子价格均为 0：焊装涂装同日开停，缓存不用攒。',
  '⚠ 派遣法规上限 10%，20%/50% 为「派遣 + 临时工」合计口径；停工日发薪 70%/0% 为行业假设。'),
]
