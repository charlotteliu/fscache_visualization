# FSCACHE Visualization

A Streamlit app that turns folder tree text with file sizes into a WizTree-style interactive treemap.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Supported input examples

Tree-style file listings with sizes:

```text
project_root/
├── src/
│   ├── app.py  1.8 MB
│   └── parser.py (420 KB)
└── data/
    └── cache.db - 128 MB
```

The parser supports `B`, `KB`, `MB`, `GB`, and `TB` units, including `KiB`, `MiB`, `GiB`, and `TiB` variants.

Cold-page CSV exports are also supported. The `名称` column may contain a file path
and an optional code-package hierarchy after `:`, split by dots:

```csv
名称,冷页数,内存大小 (KB)
/pkgContextInfo.json:other,1,4
/resources.index:other,180,720
ets,9136,36544
ets/modules.abc,4568,18272
ets/modules.abc:ohos,4361,17444
ets/modules.abc:ohos.launchercommon,475,1900
ets/modules.abc:ohos.launchercommon.src,475,1900
```
