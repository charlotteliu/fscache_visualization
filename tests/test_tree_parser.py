from tree_parser import flatten_tree, human_size, parse_size, parse_tree_text


def test_parse_tree_text_rolls_up_folder_sizes():
    root = parse_tree_text(
        """root/
├── src/
│   ├── app.py  1 MB
│   └── parser.py (512 KB)
└── data/
    └── cache.db - 2 GB
"""
    )

    rows = {row["path"]: row for row in flatten_tree(root)}

    assert root.name == "root"
    assert rows["root/src/app.py"]["size_bytes"] == 1024**2
    assert rows["root/src/parser.py"]["size_bytes"] == 512 * 1024
    assert rows["root/src"]["size_bytes"] == 1024**2 + 512 * 1024
    assert rows["root/data/cache.db"]["size_bytes"] == 2 * 1024**3
    assert root.total_size() == 2 * 1024**3 + 1024**2 + 512 * 1024


def test_size_parser_supports_commas_and_binary_units():
    assert parse_size("1,024", "KB") == 1024 * 1024
    assert parse_size("1.5", "GiB") == int(1.5 * 1024**3)
    assert human_size(1536) == "1.5 KB"
