# FSCACHE Visualization

A Streamlit app that turns folder tree text with file sizes or cold-page CSV data into a WizTree-style interactive treemap.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Supported input examples

### Folder tree text

```text
project_root/
├── src/
│   ├── app.py  1.8 MB
│   └── parser.py (420 KB)
└── data/
    └── cache.db - 128 MB
```

The tree parser supports `B`, `KB`, `MB`, `GB`, and `TB` units, including `KiB`, `MiB`, `GiB`, and `TiB` variants.

### Cold-page CSV

```csv
名称,冷页数,内存大小 (KB)
ets,9321,37284
ets/modules.abc,9321,37284
ets/modules.abc:hms-ai.Constants,,0
ets/modules.abc:hms-ai.pdkfull.src.main.ets.utils.ResCode,,4
pkgContextInfo.json,1,4
resources.index,180,720
```

For cold-page CSV input, names before `:` are split as file paths with `/`, and names after `:` are expanded as package/class paths with `.`. For example, `ets/modules.abc:hms-ai.pdkfull.src.main.ets.utils.ResCode` becomes an expandable hierarchy from `ets/modules.abc` down through package nodes to the `ResCode` class.
