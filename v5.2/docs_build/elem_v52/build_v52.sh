set -e
cd /workspace/review
python3 elem_build/v52/patch_v52.py
B=elem_build/docx; OUT=/workspace/review/产量成本模型-要素拆解-v5.2
{ printf -- '---\ntitle: "产量成本模型：要素拆解与关联设计（v5.2 版）"\nsubtitle: "VCS 产量成本模拟器配套文档 · 示例数据，非沃尔沃真实数据"\ndate: "2026-10-18"\nlang: zh-CN\ntoc-title: "目录"\n---\n\n'; tail -n +2 "$OUT.md"; } > $B/src_v52.md
P=/home/box/.local/lib/python3.13/site-packages/pypandoc/files/pandoc
$P $B/src_v52.md -f markdown-tex_math_dollars -t docx --toc --toc-depth=2 --resource-path=/workspace/review --reference-doc=manual_build/reference.docx -o $B/raw_v52.docx
python3 manual_build/post.py $B/raw_v52.docx "$OUT.docx"
timeout 600 soffice --headless --convert-to pdf "$OUT.docx" --outdir /workspace/review >/dev/null 2>&1
pdfinfo "$OUT.pdf" | grep Pages
