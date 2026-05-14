# FSCACHE Visualization

A Streamlit app that turns hierarchy data into an interactive WizTree-style treemap. It supports both file tree text with file sizes and ArkTS/Harmony-style module CSV rows with method-size totals.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Module CSV input

Choose **Module CSV** in the sidebar and paste CSV data with these columns:

```csv
"module_offset","module_name","total_method_size"
"1323932","L&@hms-core/ml-base/src/main/ets/com/huawei/mlkit/Analyzer&0.0.1-569;","2282"
"1324429","L&@hms-core/ml-rpc/src/main/ets/com/huawei/mlkit/rpc/MLRpcCallbackStub&0.0.1-569;","5579"
```

The app normalizes descriptors like `L&@scope/module/src/main/ets/com/example/Foo&1.0.0;` into this treemap hierarchy:

```text
modules
└── @scope/module
    └── com/example
        └── Foo (total_method_size)
```

Rows without `src/main/ets` are still grouped by module, for example `L&@ohos/aisuggestion/index&1.0.0;` becomes `modules/@ohos/aisuggestion/index`.

## File tree input

Choose **文件树** in the sidebar and paste tree text such as:

```text
project_root/
├── src/
│   ├── app.py  1.8 MB
│   └── parser.py (420 KB)
└── data/
    └── cache.db - 128 MB
```

The file-tree parser supports `B`, `KB`, `MB`, `GB`, and `TB` units, including `KiB`, `MiB`, `GiB`, and `TiB` variants.
