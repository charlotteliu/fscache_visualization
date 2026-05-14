from app import (
    TEXT_COLOR,
    build_tree_chart,
    build_treemap,
    prepare_visualization_data,
)
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


def test_prepare_visualization_data_truncates_long_labels_and_scales_font():
    root = parse_tree_text(
        """root/
└── exceptionally_long_first_level_filename_that_should_not_overflow.bin  12 MB
"""
    )

    df = prepare_visualization_data(flatten_tree(root), max_depth=6)
    long_file = df[df["name"].str.startswith("exceptionally_long")].iloc[0]
    root_row = df[df["name"] == "root"].iloc[0]

    assert long_file["display_name"].endswith("…")
    assert len(long_file["display_name"]) < len(long_file["name"])
    assert long_file["font_size"] < root_row["font_size"]


def test_build_visualizations_use_readable_text_and_depth_colors():
    rows = sample_rows()

    treemap = build_treemap(rows, max_depth=6)
    tree_chart = build_tree_chart(rows, max_depth=6)

    assert treemap.data[0].type == "treemap"
    assert tree_chart.data[0].type == "icicle"
    assert treemap.data[0].textfont.color == TEXT_COLOR
    assert tree_chart.data[0].textfont.color == TEXT_COLOR
    assert len(set(treemap.data[0].textfont.size)) > 1
    assert min(treemap.data[0].textfont.size) >= 10
