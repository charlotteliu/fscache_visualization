from app import build_tree_chart, build_treemap, prepare_visualization_data
from tree_parser import flatten_tree, parse_tree_text


def sample_rows():
    root = parse_tree_text(
        """root/
├── src/
│   └── app.py  1 MB
└── data/
    └── cache.db  2 MB
"""
    )
    return flatten_tree(root)


def test_prepare_visualization_data_adds_depth_labels_and_limits_depth():
    df = prepare_visualization_data(sample_rows(), max_depth=1)

    assert set(df["depth"].unique()) == {0, 1}
    assert set(df["depth_label"].unique()) == {"第 1 层", "第 2 层"}
    assert "root/src/app.py" not in set(df["path"])


def test_build_visualizations_use_larger_text_and_depth_colors():
    rows = sample_rows()

    treemap = build_treemap(rows, max_depth=6)
    tree_chart = build_tree_chart(rows, max_depth=6)

    assert treemap.data[0].type == "treemap"
    assert tree_chart.data[0].type == "icicle"
    assert treemap.data[0].textfont.size == 18
    assert tree_chart.data[0].textfont.size == 18
