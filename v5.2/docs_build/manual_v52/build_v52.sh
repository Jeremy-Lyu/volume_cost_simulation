set -e
cd /workspace/review/manual_build
python3 v52/edits_v52.py
OUT=/workspace/review/工厂运营理论与计算手册-v5.2
{ printf -- '---\ntitle: "汽车工厂运营理论与计算手册（v5.2 版）"\nsubtitle: "VCS 产量成本测算系统配套参考 · 示例数据，非沃尔沃真实数据"\nauthor: "VCS 项目组"\ndate: "2026-10-18"\nlang: zh-CN\ntoc-title: "目录"\n---\n\n'; for f in md_v52/*.md; do cat "$f"; printf '\n\n'; done; } > "$OUT.md"
P=/home/box/.local/lib/python3.13/site-packages/pypandoc/files/pandoc
$P "$OUT.md" -f markdown-tex_math_dollars -t docx --toc --toc-depth=3 --reference-doc=reference.docx -o raw.docx
python3 post.py raw.docx "$OUT.docx"
cd /workspace/review && soffice --headless --convert-to pdf "$OUT.docx" --outdir /workspace/review >/dev/null 2>&1
pdfinfo "$OUT.pdf" | grep Pages
timeout 300 soffice --headless "macro:///Standard.TocUpdate.UpdateAndSave(\"$OUT.docx\",\"/workspace/review/manual_build/toc_lo_v52.docx\",\"$OUT.pdf\")"
pdfinfo "$OUT.pdf" | grep Pages
cp "$OUT.docx" /workspace/review/manual_build/pandoc_version_v52.docx
cp /workspace/review/manual_build/toc_lo_v52.docx "$OUT.docx"
