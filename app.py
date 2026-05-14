from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.express as px
import streamlit as st

from tree_parser import flatten_tree, human_count, human_size, parse_module_csv_text, parse_tree_text


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


SAMPLE_MODULE_CSV = '''"module_offset","module_name","total_method_size"
"1323932","L&@hms-core/ml-base/src/main/ets/com/huawei/mlkit/Analyzer&0.0.1-569;","2282"
"1324429","L&@hms-core/ml-rpc/src/main/ets/com/huawei/mlkit/rpc/MLRpcCallbackStub&0.0.1-569;","5579"
"1325241","L&@hms-core/ml-rpc/src/main/ets/com/huawei/mlkit/rpc/PictureSequence&0.0.1-569;","278"
"1325553","L&@hms-core/ml-rpc/src/main/ets/com/huawei/mlkit/rpc/PixelMapSequence&0.0.1-569;","278"
"1325866","L&@hms-core/ml-rpc/src/main/ets/com/huawei/mlkit/rpc/RpcConstant&0.0.1-569;","7808"
"1326396","L&@hms-core/ml-utils/src/main/ets/com/huawei/mlkit/util/SmartLog&0.0.1-569;","564"
"1326834","L&@hms-core/ml-utils/src/main/ets/com/huawei/mlkit/util/TextUtils&0.0.1-569;","585"
"1327246","L&@ohos/airplanecomponent/src/main/ets/default/common/Constants&1.0.0;","117"
"1327629","L&@ohos/airplanecomponent/src/main/ets/default/controller/AirplaneController&1.0.0;","3436"
"1328804","L&@ohos/aisuggestion/index&1.0.0;","0"
"1328955","L&@ohos/aisuggestion/src/main/ets/default/animation/AiSuggestionAnimHelper&1.0.0;","1871"
"1329345","L&@ohos/aisuggestion/src/main/ets/default/bean/AiSuggestionComponentData&1.0.0;","1190"
"1329576","L&@ohos/aisuggestion/src/main/ets/default/bean/AiSuggestionReportParams&1.0.0;","1369"
"1330103","L&@ohos/aisuggestion/src/main/ets/default/bean/FormStackEventDonateInfo&1.0.0;","77"
"1330333","L&@ohos/aisuggestion/src/main/ets/default/bean/InputComposedData&1.0.0;","190"
"1330583","L&@ohos/aisuggestion/src/main/ets/default/bean/LauncherCardInfo&1.0.0;","1105"
"1333116","L&@ohos/aisuggestion/src/main/ets/default/command/BaseCommand&1.0.0;","452"
"1333471","L&@ohos/aisuggestion/src/main/ets/default/command/CommandConsumer&1.0.0;","2150"
"1334298","L&@ohos/aisuggestion/src/main/ets/default/command/CommandList&1.0.0;","3478"
"1335341","L&@ohos/aisuggestion/src/main/ets/default/command/CommandValidator&1.0.0;","3105"
"1336316","L&@ohos/aisuggestion/src/main/ets/default/command/imp/AddFormToFormStackCommand&1.0.0;","3520"
'''


def calculate_depth(path: str) -> int:
    return path.count("/")


def build_treemap(rows: Iterable[dict[str, object]], max_depth: int, value_label_column: str = "size_label") -> px.treemap:
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
        custom_data=["path", value_label_column, "kind", "children"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]}",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Path: %{customdata[0]}<br>"
            "Type: %{customdata[2]}<br>"
            "Size: %{customdata[1]}<br>"
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
          <h1>🧊 层级块状图可视化</h1>
          <p>支持文件树磁盘占用，也支持 module_offset/module_name/total_method_size CSV，展示模块内部 package 与 class 的方法体大小层级。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("输入与显示")
        input_mode = st.radio("输入类型", ["Module CSV", "文件树"], horizontal=True)
        use_sample = st.toggle("使用示例数据", value=True)
        max_depth = st.slider("可视化层级深度", min_value=1, max_value=10, value=6)
        if input_mode == "Module CSV":
            st.caption("CSV 需包含 `module_offset`、`module_name`、`total_method_size` 三列。")
        else:
            st.caption("支持 `├── file  12 MB`、`file - 12 MB`、`file (12 MB)` 等格式。")

    is_module_mode = input_mode == "Module CSV"
    default_text = SAMPLE_MODULE_CSV if use_sample and is_module_mode else SAMPLE_TREE if use_sample else ""
    input_text = st.text_area(
        "Module CSV" if is_module_mode else "文件夹树状文本",
        value=default_text,
        height=330,
        placeholder=(
            '"module_offset","module_name","total_method_size"\n'
            '"1323932","L&@hms-core/ml-base/src/main/ets/com/huawei/mlkit/Analyzer&0.0.1-569;","2282"'
            if is_module_mode
            else "粘贴 tree 命令输出，例如：\nroot/\n├── data/\n│   └── cache.db  128 MB\n└── README.md  24 KB"
        ),
    )

    if not input_text.strip():
        st.info("请在上方输入数据，或打开侧边栏中的示例数据。")
        return

    root = parse_module_csv_text(input_text) if is_module_mode else parse_tree_text(input_text)
    rows = flatten_tree(root)
    data = pd.DataFrame(rows)
    leaf_kind = "Class" if is_module_mode else "File"
    group_kinds = ["Module", "Package"] if is_module_mode else ["Folder"]
    leaves = data[data["kind"] == leaf_kind].copy()
    groups = data[data["kind"].isin(group_kinds)].copy()
    total_size = int(root.total_size())
    value_label_column = "method_size_label" if is_module_mode else "size_label"

    metric_cols = st.columns(4)
    metric_values = [
        ("总方法大小" if is_module_mode else "总占用", human_count(total_size, "") if is_module_mode else human_size(total_size), "total_method_size 汇总" if is_module_mode else "当前输入树的累计文件大小"),
        ("Class 数" if is_module_mode else "文件数", f"{len(leaves):,}", "CSV 中的 class 叶子节点" if is_module_mode else "含大小的叶子节点"),
        ("Module 数" if is_module_mode else "文件夹数", f"{data[data['kind'] == 'Module']['name'].nunique():,}" if is_module_mode else f"{max(len(groups) - 1, 0):,}", "按 @scope/module 聚合" if is_module_mode else "不含虚拟根节点"),
        ("最大 Class" if is_module_mode else "最大文件", leaves.sort_values("size_bytes", ascending=False).iloc[0][value_label_column] if not leaves.empty else "0", "单个 class total_method_size 峰值" if is_module_mode else "单个文件峰值"),
    ]
    for col, (label, value, help_text) in zip(metric_cols, metric_values):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='small-muted'>{label}</div><h2>{value}</h2><div class='small-muted'>{help_text}</div></div>",
                unsafe_allow_html=True,
            )

    st.subheader("Module / Package / Class 块状图" if is_module_mode else "文件块状图")
    chart_rows = [row for row in rows if int(row["size_bytes"]) > 0 or row["path"] == root.path]
    if total_size <= 0:
        st.warning("所有 total_method_size 都为 0，无法按面积绘制块状图。" if is_module_mode else "所有文件大小都为 0，无法按面积绘制块状图。")
    else:
        st.plotly_chart(build_treemap(chart_rows, max_depth, value_label_column), use_container_width=True, config={"displaylogo": False})

    left, right = st.columns([1.1, 0.9])
    with left:
        st.subheader("Top Class" if is_module_mode else "Top 大文件")
        if leaves.empty:
            st.warning("没有解析到 class。请检查 CSV 表头与 module_name 格式。" if is_module_mode else "没有解析到带 size 的文件。请检查输入格式。")
        else:
            top_leaves = leaves.sort_values("size_bytes", ascending=False).head(20)
            columns = ["name", "path", value_label_column, "size_bytes"]
            if is_module_mode:
                columns.append("module_offset")
            st.dataframe(
                top_leaves[columns],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "name": "Class" if is_module_mode else "文件名",
                    "path": "层级路径" if is_module_mode else "路径",
                    value_label_column: "方法大小" if is_module_mode else "大小",
                    "size_bytes": st.column_config.NumberColumn("total_method_size" if is_module_mode else "字节", format="%d"),
                    "module_offset": "module_offset",
                },
            )
    with right:
        st.subheader("Package / Module 排行" if is_module_mode else "目录占用排行")
        group_rank = groups[groups["parent"] != ""].sort_values("size_bytes", ascending=False).head(12)
        st.dataframe(
            group_rank[["name", "path", value_label_column, "children"]],
            use_container_width=True,
            hide_index=True,
            column_config={"name": "Package/Module" if is_module_mode else "目录", "path": "路径", value_label_column: "累计方法大小" if is_module_mode else "累计大小", "children": "直接子项"},
        )


if __name__ == "__main__":
    main()
