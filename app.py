from __future__ import annotations

from html import escape
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from tree_parser import flatten_tree, human_size, parse_tree_text


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


def calculate_depth(path: str) -> int:
    return path.count("/")


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
        custom_data=["path", "size_label", "kind", "children", "cold_pages"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]}",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Path: %{customdata[0]}<br>"
            "Type: %{customdata[2]}<br>"
            "Size: %{customdata[1]}<br>"
            "Cold pages: %{customdata[4]}<br>"
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


def build_export_html(fig: object, title: str = "大桌面未访问文件页溯源分析") -> str:
    """Build a standalone HTML export that keeps Plotly treemap interactions."""
    chart_html = fig.to_html(
        full_html=True,
        include_plotlyjs=True,
        config={"displaylogo": False, "responsive": True},
    )
    return chart_html.replace(
        "<head>",
        (
            "<head>"
            f"<title>{escape(title)}</title>"
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<style>"
            "body{margin:0;background:#F8FAFC;font-family:Arial,Helvetica,sans-serif;}"
            ".export-header{padding:18px 24px;background:linear-gradient(135deg,#102A68,#1D4ED8 55%,#38BDF8);color:white;}"
            ".export-header h1{margin:0;font-size:24px;}"
            ".export-header p{margin:6px 0 0;color:#DBEAFE;}"
            ".plotly-graph-div{height:calc(100vh - 92px) !important;}"
            "</style>"
        ),
        1,
    ).replace(
        "<body>",
        (
            '<body><div class="export-header">'
            "<h1>🧊 大桌面未访问文件页溯源分析</h1>"
            "<p>单击块可展开/聚焦目录，双击或点击路径可返回上级视图。</p>"
            "</div>"
        ),
        1,
    )


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
    st.set_page_config(page_title="大桌面未访问文件页溯源分析", page_icon="🧊", layout="wide")
    render_styles()

    st.markdown(
        """
        <div class="hero-card">
          <h1>🧊 大桌面未访问文件页溯源分析</h1>
          <p>粘贴文件夹树状文本和文件大小，立即生成可交互的磁盘占用块状图，快速定位大文件与热点目录。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("输入与显示")
        use_sample = st.toggle("使用示例数据", value=True)
        max_depth = st.slider("可视化层级深度", min_value=1, max_value=8, value=6)
        st.caption(
            "支持 tree 文本，以及 `名称,冷页数,内存大小 (KB)` 冷页 CSV；"
            "CSV 名称列可包含 `path:pkg.subpkg` 代码包层级。"
        )

    default_text = SAMPLE_TREE if use_sample else ""
    tree_text = st.text_area(
        "文件夹树状文本或冷页 CSV",
        value=default_text,
        height=300,
        placeholder=(
            "粘贴 tree 命令输出，例如：\nroot/\n├── data/\n"
            "│   └── cache.db  128 MB\n└── README.md  24 KB\n\n"
            "或冷页 CSV：\n名称,冷页数,内存大小 (KB)\nets/modules.abc:ohos.launchercommon.src,475,1900"
        ),
    )

    if not tree_text.strip():
        st.info("请在上方输入文件夹树状文本或冷页 CSV，或打开侧边栏中的示例数据。")
        return

    root = parse_tree_text(tree_text)
    rows = flatten_tree(root)
    data = pd.DataFrame(rows)
    files = data[data["kind"] == "File"].copy()
    folders = data[data["kind"] == "Folder"].copy()
    total_size = int(root.total_size())

    has_cold_pages = "cold_pages" in data.columns and data["cold_pages"].notna().any()
    metric_cols = st.columns(5 if has_cold_pages else 4)
    metric_values = [
        ("总占用", human_size(total_size), "当前输入树的累计文件大小"),
        ("文件数", f"{len(files):,}", "含大小的叶子节点"),
        ("文件夹数", f"{max(len(folders) - 1, 0):,}", "不含虚拟根节点"),
        (
            "最大文件",
            files.sort_values("size_bytes", ascending=False).iloc[0]["size_label"]
            if not files.empty
            else "0 B",
            "单个文件峰值",
        ),
    ]
    if has_cold_pages:
        top_level_cold_pages = data.loc[
            data["parent"] == root.path, "cold_pages"
        ].fillna(0)
        metric_values.insert(
            1,
            (
                "总冷页",
                f"{int(root.cold_pages or top_level_cold_pages.sum()):,}",
                "CSV 输入中的冷页数",
            ),
        )
    for col, (label, value, help_text) in zip(metric_cols, metric_values):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div><h2>{value}</h2><div class='small-muted'>{help_text}</div></div>",
                unsafe_allow_html=True,
            )

    st.subheader("文件块状图")
    treemap_fig = build_treemap(rows, max_depth)
    st.plotly_chart(
        treemap_fig, use_container_width=True, config={"displaylogo": False}
    )
    st.download_button(
        "⬇️ 导出块状图 HTML",
        data=build_export_html(treemap_fig),
        file_name="fscache_treemap.html",
        mime="text/html",
        help="导出的 HTML 内置 Plotly，可离线打开并保留单击块展开/聚焦的交互。",
    )

    left, right = st.columns([1.1, 0.9])
    with left:
        st.subheader("Top 大文件")
        if files.empty:
            st.warning("没有解析到带 size 的文件。请检查输入格式。")
        else:
            top_files = files.sort_values("size_bytes", ascending=False).head(20)
            top_columns = ["name", "path", "size_label", "size_bytes"]
            column_config = {
                "name": "文件名",
                "path": "路径",
                "size_label": "大小",
                "size_bytes": st.column_config.NumberColumn("字节", format="%d"),
            }
            if has_cold_pages:
                top_columns.insert(3, "cold_pages")
                column_config["cold_pages"] = st.column_config.NumberColumn(
                    "冷页数", format="%d"
                )
            st.dataframe(
                top_files[top_columns],
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
            )
    with right:
        st.subheader("目录占用排行")
        folder_rank = (
            folders[folders["parent"] != ""]
            .sort_values("size_bytes", ascending=False)
            .head(12)
        )
        st.dataframe(
            folder_rank[["name", "path", "size_label", "children"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": "目录",
                "path": "路径",
                "size_label": "累计大小",
                "children": "直接子项",
            },
        )


if __name__ == "__main__":
    main()
