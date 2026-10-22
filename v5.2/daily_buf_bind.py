"""v5.2：整班开/整天停、派遣 50%、月需求 6,000 时，白车身库容压到多少开始卡住（示例数据 ⚠）
nohup python3 daily_buf_bind.py > output/logs/buf_bind.log 2>&1 &"""
import os, multiprocessing as mp
import daily_flex_sweep as fs, daily as dy
if __name__ == "__main__":
    X = {"same_shift_as_crew": True}
    jobs = [(0.5, b, "optimal", X) for b in (200, 150, 120, 100)]
    with mp.get_context("spawn").Pool(2) as p: rows = p.map(fs.one, jobs)
    dy.wcsv(os.path.join(dy.OUT, "daily_buffer_bind.csv"), rows)
    for r in rows: print(r)
