from tree_parser import flatten_tree, human_size, parse_module_csv_text, parse_size, parse_tree_text


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


def test_parse_ascii_plus_tree_with_windows_root_and_byte_sizes():
    root = parse_tree_text(
        r"D:\hm_test\文件页负载分析\trace工具\sceneboard\SceneBoard\n"
        r"+-- ets/\n"
        r"    +-- .vscode/\n"
        r"        +-- ut/\n"
        r"        |-- settings.json  [46 B]\n"
        r"        |-- tags-34.wecode-db  [132.00 KB]\n"
        r"        |-- tags-34.wecode-lock  [4.00 KB]\n"
        r"    +-- common/\n"
        r"        +-- animation/\n"
        r"            |-- appear.json  [1.64 KB]\n"
    )

    rows = {row["path"]: row for row in flatten_tree(root)}
    root_path = r"D:\hm_test\文件页负载分析\trace工具\sceneboard\SceneBoard"

    assert root.name == root_path
    assert rows[f"{root_path}/ets/.vscode/settings.json"]["size_bytes"] == 46
    assert (
        rows[f"{root_path}/ets/.vscode/tags-34.wecode-db"]["size_bytes"]
        == 132 * 1024
    )
    assert (
        rows[f"{root_path}/ets/.vscode/tags-34.wecode-lock"]["size_bytes"]
        == 4 * 1024
    )
    assert rows[f"{root_path}/ets/common/animation/appear.json"][
        "size_bytes"
    ] == int(1.64 * 1024)
    assert rows[f"{root_path}/ets/.vscode/ut"]["kind"] == "Folder"
    assert (
        rows[f"{root_path}/ets/.vscode"]["size_bytes"]
        == 46 + 132 * 1024 + 4 * 1024
    )


def test_parse_ascii_plus_tree_with_actual_newlines():
    root = parse_tree_text(
        """D:\\root
+-- ets/
    +-- common/
        |-- icon.png  [6.63 KB]
"""
    )

    rows = {row["path"]: row for row in flatten_tree(root)}

    assert rows[r"D:\root/ets/common/icon.png"]["size_bytes"] == int(6.63 * 1024)


def test_parse_module_csv_builds_module_package_class_hierarchy():
    root = parse_module_csv_text(
        '"module_offset","module_name","total_method_size"\n'
        '"1323932","L&@hms-core/ml-base/src/main/ets/com/huawei/mlkit/Analyzer&0.0.1-569;","2282"\n'
        '"1324429","L&@hms-core/ml-rpc/src/main/ets/com/huawei/mlkit/rpc/MLRpcCallbackStub&0.0.1-569;","5579"\n'
        '"1328804","L&@ohos/aisuggestion/index&1.0.0;","0"\n'
    )

    rows = {row["path"]: row for row in flatten_tree(root)}

    assert root.name == "modules"
    assert rows["modules/@hms-core/ml-base/com/huawei/mlkit/Analyzer"]["kind"] == "Class"
    assert rows["modules/@hms-core/ml-base/com/huawei/mlkit/Analyzer"]["size_bytes"] == 2282
    assert rows["modules/@hms-core/ml-rpc/com/huawei/mlkit/rpc"]["kind"] == "Package"
    assert rows["modules/@hms-core/ml-rpc/com/huawei/mlkit/rpc"]["size_bytes"] == 5579
    assert rows["modules/@ohos/aisuggestion/index"]["kind"] == "Class"
    assert rows["modules/@ohos/aisuggestion/index"]["module_offset"] == "1328804"
    assert rows["modules/@hms-core/ml-base"]["kind"] == "Module"
    assert root.total_size() == 2282 + 5579
