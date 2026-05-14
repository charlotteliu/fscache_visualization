from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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


SIZE_COLOR_SCALE = ["#D7F3FF", "#61C4F2", "#246BFE", "#11376D"]
DEPTH_COLORS = [
    "#2563EB",
    "#0891B2",
    "#16A34A",
    "#CA8A04",
    "#EA580C",
    "#DC2626",
    "#9333EA",
    "#475569",
]
TEXT_COLOR = "#F8FAFC"
BORDER_COLOR = "rgba(255, 255, 255, .92)"


def calculate_depth(path: str) -> int:
    return path.count("/")


def truncate_label(label: str, max_chars: int) -> str:
    if len(label) <= max_chars:
        return label
    return f"{label[: max(max_chars - 1, 1)]}…"


def calculate_label_budget(depth: int, size_share: float) -> int:
    base_budget = max(12, 32 - depth * 2)
    if size_share >= 0.25:
        return base_budget + 12
    if size_share >= 0.08:
        return base_budget + 6
    if size_share >= 0.03:
        return base_budget
    return max(10, base_budget - 6)


def calculate_font_size(label: str, depth: int, size_share: float) -> int:
    size = max(14, 19 - depth)
    if size_share < 0.015:
        size = min(size, 12)
    elif size_share < 0.04:
        size = min(size, 13)
    elif size_share < 0.1:
        size = min(size, 15)

    if len(label) > 42:
        size = min(size, 13)
    elif len(label) > 28:
        size = min(size, 15)

    return size


def prepare_visualization_data(
    rows: Iterable[dict[str, object]], max_depth: int
) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[df["size_bytes"] > 0].copy()
    if df.empty:
        df["depth"] = pd.Series(dtype="int")
        df["depth_label"] = pd.Series(dtype="str")
        df["size_share"] = pd.Series(dtype="float")
        df["display_name"] = pd.Series(dtype="str")
        df["font_size"] = pd.Series(dtype="int")
        df["text_color"] = pd.Series(dtype="str")
        return df

    root_depth = int(df["path"].str.count("/").min())
    total_size = float(df["size_bytes"].max())
    df["depth"] = df["path"].apply(calculate_depth) - root_depth
    df["depth_label"] = df["depth"].apply(lambda depth: f"第 {depth + 1} 层")
    df["size_share"] = df["size_bytes"].apply(lambda size: float(size) / total_size)
    df["display_name"] = df.apply(
        lambda row: truncate_label(
            str(row["name"]), calculate_label_budget(int(row["depth"]), row["size_share"])
        ),
        axis=1,
    )
    df["font_size"] = df.apply(
        lambda row: calculate_font_size(
            str(row["name"]), int(row["depth"]), row["size_share"]
        ),
        axis=1,
    )
    df["text_color"] = df["size_share"].apply(
        lambda share: TEXT_COLOR if share >= 0.18 else "#0F172A"
    )

    if max_depth:
        df = df[df["depth"] <= max_depth]

    return df


def apply_chart_layout(
    fig: go.Figure, font_sizes: Iterable[int], font_colors: Iterable[str] | str
) -> go.Figure:
    fig.update_traces(
        texttemplate="<b>%{customdata[4]}</b><br><span>%{customdata[1]}</span>",
        textfont=dict(size=list(font_sizes), color=font_colors),
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Path: %{customdata[0]}<br>"
            "Type: %{customdata[2]}<br>"
            "Size: %{customdata[1]}<br>"
            "Children: %{customdata[3]}<extra></extra>"
        ),
        marker=dict(line=dict(color=BORDER_COLOR, width=1)),
    )
    fig.update_traces(
        selector=dict(type="treemap"),
        marker=dict(
            cornerradius=7,
            line=dict(color=BORDER_COLOR, width=1),
        ),
        tiling=dict(pad=4),
    )
    fig.update_layout(
        margin=dict(t=8, l=8, r=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        uniformtext=dict(minsize=11, mode="hide"),
        height=680,
    )
    return fig


def build_treemap(rows: Iterable[dict[str, object]], max_depth: int) -> go.Figure:
    df = prepare_visualization_data(rows, max_depth)

    fig = px.treemap(
        df,
        ids="path",
        names="name",
        parents="parent",
        values="size_bytes",
        color="size_bytes",
        color_continuous_scale=SIZE_COLOR_SCALE,
        custom_data=["path", "size_label", "kind", "children", "display_name"],
    )
    fig.update_layout(coloraxis_showscale=False)
    return apply_chart_layout(fig, df["font_size"], df["text_color"].tolist())


def build_tree_chart(rows: Iterable[dict[str, object]], max_depth: int) -> go.Figure:
    df = prepare_visualization_data(rows, max_depth)

    fig = px.icicle(
        df,
        ids="path",
        names="name",
        parents="parent",
        values="size_bytes",
        color="depth_label",
        color_discrete_sequence=DEPTH_COLORS,
        custom_data=["path", "size_label", "kind", "children", "display_name"],
    )
    fig.update_traces(root_color="#0F172A")
    return apply_chart_layout(fig, df["font_size"], TEXT_COLOR)


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
        use_sample = st.toggle("使用示例数据", value=True)
        max_depth = st.slider("可视化层级深度", min_value=1, max_value=8, value=6)
        if "chart_mode" not in st.session_state:
            st.session_state.chart_mode = "treemap"
        st.caption("视图切换")
        mode_cols = st.columns(2)
        if mode_cols[0].button(
            "块状图",
            use_container_width=True,
            type="primary" if st.session_state.chart_mode == "treemap" else "secondary",
        ):
            st.session_state.chart_mode = "treemap"
        if mode_cols[1].button(
            "树状图",
            use_container_width=True,
            type="primary" if st.session_state.chart_mode == "tree" else "secondary",
        ):
            st.session_state.chart_mode = "tree"
        st.caption("支持 `├── file  12 MB`、`file - 12 MB`、`file (12 MB)` 等格式。")

    default_text = SAMPLE_TREE if use_sample else ""
    tree_text = st.text_area(
        "文件夹树状文本",
        value=default_text,
        height=300,
        placeholder="粘贴 tree 命令输出，例如：\nroot/\n├── data/\n│   └── cache.db  128 MB\n└── README.md  24 KB",
    )

    if not tree_text.strip():
        st.info("请在上方输入文件夹树状文本，或打开侧边栏中的示例数据。")
        return

    root = parse_tree_text(tree_text)
    rows = flatten_tree(root)
    data = pd.DataFrame(rows)
    files = data[data["kind"] == "File"].copy()
    folders = data[data["kind"] == "Folder"].copy()
    total_size = int(root.total_size())

    metric_cols = st.columns(4)
    metric_values = [
        ("总占用", human_size(total_size), "当前输入树的累计文件大小"),
        ("文件数", f"{len(files):,}", "含大小的叶子节点"),
        ("文件夹数", f"{max(len(folders) - 1, 0):,}", "不含虚拟根节点"),
        ("最大文件", files.sort_values("size_bytes", ascending=False).iloc[0]["size_label"] if not files.empty else "0 B", "单个文件峰值"),
    ]
    for col, (label, value, help_text) in zip(metric_cols, metric_values):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div><h2>{value}</h2><div class='small-muted'>{help_text}</div></div>",
                unsafe_allow_html=True,
            )

    chart_mode = st.session_state.get("chart_mode", "treemap")
    if chart_mode == "tree":
        st.subheader("文件树状图")
        figure = build_tree_chart(rows, max_depth)
    else:
        st.subheader("文件块状图")
        figure = build_treemap(rows, max_depth)
    st.plotly_chart(figure, use_container_width=True, config={"displaylogo": False})

    left, right = st.columns([1.1, 0.9])
    with left:
        st.subheader("Top 大文件")
        if files.empty:
            st.warning("没有解析到带 size 的文件。请检查输入格式。")
        else:
            top_files = files.sort_values("size_bytes", ascending=False).head(20)
            st.dataframe(
                top_files[["name", "path", "size_label", "size_bytes"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "name": "文件名",
                    "path": "路径",
                    "size_label": "大小",
                    "size_bytes": st.column_config.NumberColumn("字节", format="%d"),
                },
            )
    with right:
        st.subheader("目录占用排行")
        folder_rank = folders[folders["parent"] != ""].sort_values("size_bytes", ascending=False).head(12)
        st.dataframe(
            folder_rank[["name", "path", "size_label", "children"]],
            use_container_width=True,
            hide_index=True,
            column_config={"name": "目录", "path": "路径", "size_label": "累计大小", "children": "直接子项"},
        )


if __name__ == "__main__":
    main()
