from app import build_export_html, build_treemap
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
    assert "单击块可展开/聚焦目录" in html
    assert "cache.db" in html
