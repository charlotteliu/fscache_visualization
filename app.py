from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from tree_parser import flatten_tree, human_size, parse_input_text

SAMPLE_TREE = """project_root/
├── src/
│   ├── app.py  1.8 MB
│   ├── components/
│   │   ├── treemap.py  730 KB
│   │   └── parser.py  420 KB
│   └── assets/
│       ├── hero.png  4.2 MB
│       └── logo.svg  95 KB
├── data/
│   ├── cache.db  128 MB
│   ├── events.parquet  310 MB
│   └── exports/
│       ├── report_2026_01.csv  32 MB
│       ├── report_2026_02.csv  29 MB
│       └── raw_backup.zip  1.4 GB
├── notebooks/
│   ├── analysis.ipynb  16 MB
│   └── experiments.ipynb  44 MB
├── tests/
│   ├── test_parser.py  310 KB
│   └── test_ui.py  270 KB
└── README.md  24 KB
"""

SAMPLE_COLD_PAGE_CSV = """名称,冷页数,内存大小 (KB)
ets,9321,37284
ets/modules.abc,9321,37284
ets/modules.abc:hms-ai.Constants,,0
ets/modules.abc:hms-ai.GlobalContext,,1
ets/modules.abc:hms-ai.ModuleInfo,,1
ets/modules.abc:hms-ai.PluginInfoManager,,3
ets/modules.abc:hms-ai.ResCode,,2
ets/modules.abc:hms-ai.pdkfull.src.main.ets.ServiceAbilityBridge,,5
ets/modules.abc:hms-ai.pdkfull.src.main.ets.abilityservice.information.PluginInfoManager,,7
ets/modules.abc:hms-ai.pdkfull.src.main.ets.utils.GlobalContext,,2
ets/modules.abc:hms-ai.pdkfull.src.main.ets.utils.ResCode,,4
pkgContextInfo.json,1,4
resources.index,180,720
"""


def calculate_depth(path: str) -> int:
    slash_depth = path.count("/")
    if ":" not in path:
        return slash_depth
    symbol_path = path.split(":", 1)[1]
    return slash_depth + symbol_path.count(".") + 1


def build_treemap(rows: Iterable[dict[str, object]], max_depth: int) -> px.treemap:
    df = pd.DataFrame(rows)
    df = df[df["size_bytes"] > 0].copy()
    if max_depth:
        root_depth = int(df["path"].str.count("/").min())
        df = df[df["path"].apply(calculate_depth) <= root_depth + max_depth]

    fig = px.treemap(
        df,
        ids="path",
        names="name",
        parents="parent",
        values="size_bytes",
        color="size_bytes",
        color_continuous_scale=["#D7F3FF", "#61C4F2", "#246BFE", "#11376D"],
        custom_data=["path", "size_label", "kind", "children", "cold_pages", "size_kb"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]}",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Path: %{customdata[0]}<br>"
            "Type: %{customdata[2]}<br>"
            "Size: %{customdata[1]}<br>"
            "Cold pages: %{customdata[4]}<br>"
            "Memory: %{customdata[5]} KB<br>"
            "Children: %{customdata[3]}<extra></extra>"
        ),
        marker=dict(cornerradius=6),
    )
    fig.update_layout(
        margin=dict(t=8, l=8, r=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        height=680,
    )
    return fig


def render_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1280px;}
            [data-testid="stSidebar"] {background: linear-gradient(180deg, #0F172A 0%, #172554 100%);}
            [data-testid="stSidebar"] * {color: #E2E8F0 !important;}
            .hero-card {
                padding: 1.4rem 1.6rem;
                border-radius: 22px;
                background: linear-gradient(135deg, #102A68 0%, #1D4ED8 48%, #38BDF8 100%);
                box-shadow: 0 20px 50px rgba(15, 23, 42, .18);
                color: white;
                margin-bottom: 1.2rem;
            }
            .hero-card h1 {margin: 0; font-size: 2.4rem; letter-spacing: -0.04em;}
            .hero-card p {margin: .45rem 0 0; color: #DBEAFE; font-size: 1.05rem;}
            .metric-card {
                padding: 1rem;
                border: 1px solid #E2E8F0;
                border-radius: 18px;
                background: #FFFFFF;
                box-shadow: 0 10px 30px rgba(15, 23, 42, .06);
            }
            .small-muted {color: #64748B; font-size: .9rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="WizTree 文件块状图", page_icon="🧊", layout="wide")
    render_styles()

    st.markdown(
        """
        <div class="hero-card">
          <h1>🧊 WizTree 风格文件空间可视化</h1>
          <p>粘贴文件夹树状文本和文件大小，立即生成可交互的磁盘占用块状图，快速定位大文件与热点目录。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("输入与显示")
        input_format_label = st.radio(
            "输入格式",
            ["自动识别", "文件树文本", "冷页 CSV"],
            horizontal=False,
        )
        use_sample = st.toggle("使用示例数据", value=True)
        max_depth = st.slider("可视化层级深度", min_value=1, max_value=12, value=6)
        st.caption(
            "文件树支持 `├── file  12 MB`；冷页 CSV 支持 `名称,冷页数,内存大小 (KB)`，并将 `abc:包.类` 展开为包/类层级。"
        )

    input_format_map = {
        "自动识别": "auto",
        "文件树文本": "tree",
        "冷页 CSV": "cold_page_csv",
    }
    selected_format = input_format_map[input_format_label]
    if use_sample and selected_format == "cold_page_csv":
        default_text = SAMPLE_COLD_PAGE_CSV
    elif use_sample:
        default_text = SAMPLE_TREE
    else:
        default_text = ""

    tree_text = st.text_area(
        "输入内容",
        value=default_text,
        height=300,
        placeholder=(
            "粘贴 tree 命令输出，或冷页 CSV：\n"
            "名称,冷页数,内存大小 (KB)\n"
            "ets/modules.abc,9321,37284\n"
            "ets/modules.abc:hms-ai.utils.JsonUtil,,1"
        ),
    )

    if not tree_text.strip():
        st.info("请在上方输入文件夹树状文本或冷页 CSV，或打开侧边栏中的示例数据。")
        return

    root = parse_input_text(tree_text, selected_format)
    rows = flatten_tree(root)
    data = pd.DataFrame(rows)
    files = data[data["kind"].isin(["File", "ABC File", "Class"])].copy()
    folders = data[~data["kind"].isin(["File", "Class"])].copy()
    total_size = int(root.total_size())

    metric_cols = st.columns(4)
    metric_values = [
        ("总占用", human_size(total_size), "当前输入树或冷页 CSV 的累计内存大小"),
        (
            "冷页数",
            f"{int(root.total_cold_pages()):,}",
            "CSV 中的冷页累计；文件树输入为 0",
        ),
        ("节点数", f"{len(data):,}", "文件、包、类和目录节点总数"),
        (
            "最大文件",
            (
                files.sort_values("size_bytes", ascending=False).iloc[0]["size_label"]
                if not files.empty
                else "0 B"
            ),
            "单个文件峰值",
        ),
    ]
    for col, (label, value, help_text) in zip(metric_cols, metric_values):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div><h2>{value}</h2><div class='small-muted'>{help_text}</div></div>",
                unsafe_allow_html=True,
            )

    st.subheader("文件块状图")
    st.plotly_chart(
        build_treemap(rows, max_depth),
        use_container_width=True,
        config={"displaylogo": False},
    )

    left, right = st.columns([1.1, 0.9])
    with left:
        st.subheader("Top 文件 / 类")
        if files.empty:
            st.warning("没有解析到带 size 的文件。请检查输入格式。")
        else:
            top_files = files.sort_values("size_bytes", ascending=False).head(20)
            st.dataframe(
                top_files[
                    [
                        "name",
                        "path",
                        "kind",
                        "cold_pages",
                        "size_label",
                        "size_kb",
                        "size_bytes",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "name": "文件名",
                    "path": "路径",
                    "kind": "类型",
                    "cold_pages": st.column_config.NumberColumn("冷页数", format="%d"),
                    "size_label": "大小",
                    "size_kb": st.column_config.NumberColumn(
                        "内存大小 (KB)", format="%d"
                    ),
                    "size_bytes": st.column_config.NumberColumn("字节", format="%d"),
                },
            )
    with right:
        st.subheader("目录 / 包占用排行")
        folder_rank = (
            folders[folders["parent"] != ""]
            .sort_values("size_bytes", ascending=False)
            .head(12)
        )
        st.dataframe(
            folder_rank[
                ["name", "path", "kind", "cold_pages", "size_label", "children"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": "目录/包",
                "path": "路径",
                "kind": "类型",
                "cold_pages": "冷页数",
                "size_label": "累计大小",
                "children": "直接子项",
            },
        )


if __name__ == "__main__":
    main()
