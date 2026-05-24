from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from tree_parser import flatten_tree, human_size, parse_tree_text


APP_TITLE = "大桌面未访问文件页溯源分析"

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


def format_cold_pages(value: float) -> str:
    return f"{int(value):,}" if float(value).is_integer() else f"{value:,.3f}"


def load_default_tree_text() -> str:
    data_file = Path("data.csv")
    if data_file.exists():
        return data_file.read_text(encoding="utf-8")
    return SAMPLE_TREE


def build_treemap(
    rows: Iterable[dict[str, object]],
    max_depth: int,
    color_metric: str = "size_bytes",
) -> px.treemap:
    df = pd.DataFrame(rows)
    df = df[df["size_bytes"] > 0].copy()
    if max_depth:
        root_depth = int(df["path"].str.count("/").min())
        df = df[df["path"].apply(calculate_depth) <= root_depth + max_depth]

    color_column = color_metric if color_metric in df.columns else "size_bytes"
    color_scale = (
        ["#F8FAFC", "#C7D2FE", "#6366F1", "#312E81"]
        if color_column == "cold_pages"
        else ["#F8FAFC", "#BAE6FD", "#0284C7", "#0F172A"]
    )

    fig = px.treemap(
        df,
        ids="path",
        names="name",
        parents="parent",
        values="size_bytes",
        color=color_column,
        color_continuous_scale=color_scale,
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
        margin=dict(t=4, l=4, r=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        height=680,
    )
    return fig


def build_export_html(fig: object, title: str = APP_TITLE) -> str:
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
            ":root{color-scheme:light;}"
            "body{margin:0;background:#F8FAFC;color:#0F172A;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;}"
            ".export-header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding:18px 24px;border-bottom:1px solid #E2E8F0;background:#FFFFFF;}"
            ".export-header h1{margin:0;font-size:22px;font-weight:700;letter-spacing:0;}"
            ".export-header p{margin:6px 0 0;color:#475569;font-size:14px;}"
            ".export-badge{border:1px solid #CBD5E1;border-radius:999px;padding:6px 10px;color:#334155;font-size:12px;white-space:nowrap;}"
            ".plotly-graph-div{height:calc(100vh - 86px) !important;}"
            "</style>"
        ),
        1,
    ).replace(
        "<body>",
        (
            '<body><div class="export-header">'
            "<div>"
            f"<h1>{escape(title)}</h1>"
            "<p>单击块可展开目录，双击或点击路径返回上级视图。</p>"
            "</div>"
            '<div class="export-badge">离线自包含导出</div>'
            "</div>"
        ),
        1,
    )


def render_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1280px;}
            [data-testid="stSidebar"] {background: #0F172A;}
            [data-testid="stSidebar"] * {color: #E2E8F0 !important;}
            [data-testid="stSidebar"] code {
                color: #0F172A !important;
                background: #E2E8F0 !important;
                border-radius: 4px;
            }
            [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {font-weight: 600;}
            div[data-testid="stDownloadButton"] button {border-radius: 8px; font-weight: 650;}
            .app-header {
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
                gap: 1.2rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid #E2E8F0;
                margin-bottom: 1.2rem;
            }
            .app-header h1 {margin: 0; font-size: 2rem; letter-spacing: 0; color: #0F172A;}
            .app-header p {margin: .45rem 0 0; color: #475569; font-size: 1rem;}
            .privacy-badge {
                border: 1px solid #CBD5E1;
                border-radius: 999px;
                padding: .45rem .7rem;
                color: #334155;
                background: #FFFFFF;
                font-size: .82rem;
                white-space: nowrap;
            }
            .metric-card {
                padding: .95rem 1rem;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: #FFFFFF;
            }
            .metric-card h2 {margin: .25rem 0; color: #0F172A; font-size: 1.45rem;}
            .small-muted {color: #64748B; font-size: .9rem;}
            .section-title {margin: 1.4rem 0 .4rem; font-size: 1.08rem; font-weight: 700; color: #0F172A;}
            .insight-panel {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 1rem;
                background: #FFFFFF;
            }
            .insight-row {
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                padding: .55rem 0;
                border-bottom: 1px solid #F1F5F9;
            }
            .insight-row:last-child {border-bottom: 0;}
            .insight-row span:first-child {color: #475569;}
            .insight-row span:last-child {font-weight: 650; color: #0F172A; text-align: right;}
            @media (max-width: 720px) {
                .app-header {display: block;}
                .privacy-badge {display: inline-block; margin-top: .8rem;}
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="▦", layout="wide")
    render_styles()

    st.markdown(
        """
        <div class="app-header">
          <div>
            <h1>大桌面未访问文件页溯源分析</h1>
            <p>面向离线排查的本地可视化工具，用于定位大文件、热点目录与冷页分布。</p>
          </div>
          <div class="privacy-badge">私有化本地运行</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("输入与显示")
        use_sample = st.toggle("使用默认数据", value=True)
        max_depth = st.slider("可视化层级深度", min_value=1, max_value=30, value=12)
        st.caption(
            "支持 tree 文本，以及 `名称,冷页数,内存大小 (KB)` 冷页 CSV；"
            "CSV 名称列可包含 `path:pkg.subpkg` 代码包层级。"
        )
        st.divider()
        st.caption("私有化配置已关闭 Streamlit 使用统计；导出的 HTML 内置 Plotly，可离线查看。")

    default_text = load_default_tree_text() if use_sample else ""
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
    color_metric = "cold_pages" if has_cold_pages else "size_bytes"
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
                format_cold_pages(float(root.cold_pages or top_level_cold_pages.sum())),
                "CSV 输入中的冷页数",
            ),
        )
    for col, (label, value, help_text) in zip(metric_cols, metric_values):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div><h2>{value}</h2><div class='small-muted'>{help_text}</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div class='section-title'>文件块状图</div>", unsafe_allow_html=True)
    treemap_fig = build_treemap(rows, max_depth, color_metric=color_metric)
    st.plotly_chart(
        treemap_fig, use_container_width=True, config={"displaylogo": False}
    )
    st.download_button(
        "导出块状图 HTML",
        data=build_export_html(treemap_fig),
        file_name="fscache_treemap.html",
        mime="text/html",
        help="导出的 HTML 内置 Plotly，可离线打开并保留单击块展开/聚焦的交互。",
    )

    left, right = st.columns([1.1, 0.9])
    with left:
        st.markdown("<div class='section-title'>Top 大文件</div>", unsafe_allow_html=True)
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
                    "冷页数", format="%.3f"
                )
            st.dataframe(
                top_files[top_columns],
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
            )
    with right:
        st.markdown("<div class='section-title'>目录占用排行</div>", unsafe_allow_html=True)
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

    if not files.empty:
        top_file = files.sort_values("size_bytes", ascending=False).iloc[0]
        top_share = (float(top_file["size_bytes"]) / total_size * 100) if total_size else 0
        folder_count = max(len(folders) - 1, 0)
        st.markdown("<div class='section-title'>分析摘要</div>", unsafe_allow_html=True)
        st.markdown(
            (
                "<div class='insight-panel'>"
                f"<div class='insight-row'><span>最大文件</span><span>{escape(str(top_file['path']))}</span></div>"
                f"<div class='insight-row'><span>最大文件占比</span><span>{top_share:.1f}%</span></div>"
                f"<div class='insight-row'><span>当前层级范围</span><span>{folder_count:,} 个目录 / {len(files):,} 个文件</span></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
