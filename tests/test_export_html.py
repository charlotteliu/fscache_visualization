from pathlib import Path

from app import build_export_html, build_treemap, load_default_tree_text
from tree_parser import flatten_tree, parse_tree_text


def test_export_html_is_standalone_and_keeps_treemap_interactions():
    root = parse_tree_text(
        """root/
├── src/
│   └── app.py  1 MB
└── data/
    └── cache.db  2 MB
"""
    )
    fig = build_treemap(flatten_tree(root), max_depth=6)

    html = build_export_html(fig)

    assert "<html>" in html
    assert "plotly.js" in html
    assert "treemap" in html
    assert "大桌面未访问文件页溯源分析" in html
    assert "单击块可展开/聚焦目录" in html
    assert "cache.db" in html


def test_load_default_tree_text_prefers_data_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expected = "名称,冷页数,内存大小(KB)\\nets,1,4\\n"
    Path("data.csv").write_text(expected, encoding="utf-8")

    assert load_default_tree_text() == expected
