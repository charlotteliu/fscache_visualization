# FSCACHE Visualization

A Streamlit app that turns folder tree text with file sizes into a WizTree-style interactive treemap.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Supported input examples

```text
project_root/
├── src/
│   ├── app.py  1.8 MB
│   └── parser.py (420 KB)
└── data/
    └── cache.db - 128 MB
```

The parser supports `B`, `KB`, `MB`, `GB`, and `TB` units, including `KiB`, `MiB`, `GiB`, and `TiB` variants.
