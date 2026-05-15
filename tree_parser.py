from __future__ import annotations

import re
from csv import DictReader, reader
from dataclasses import dataclass, field
from io import StringIO
from typing import Iterable


SIZE_UNITS = {
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024**2,
    "mib": 1024**2,
    "gb": 1024**3,
    "gib": 1024**3,
    "tb": 1024**4,
    "tib": 1024**4,
}

TREE_MARKER_RE = re.compile(
    r"(?P<indent>.*?)(?P<marker>├──|└──|┣━━|┗━━|\+--|\|--|`--|╰──|╭──)"
    r"\s*(?P<content>.*)"
)


@dataclass
class TreeNode:
    name: str
    path: str
    explicit_size: int | None = None
    cold_pages: int | None = None
    children: list["TreeNode"] = field(default_factory=list)
    parent: "TreeNode | None" = None

    @property
    def is_file(self) -> bool:
        return not self.children and self.explicit_size is not None

    def total_size(self) -> int:
        if self.explicit_size is not None:
            return self.explicit_size
        return sum(child.total_size() for child in self.children)


def parse_size(value: str | None, unit: str | None) -> int | None:
    if value is None or unit is None:
        return None
    normalized_unit = unit.lower()
    multiplier = SIZE_UNITS.get(normalized_unit)
    if multiplier is None:
        return None
    return int(float(value.replace(",", "")) * multiplier)


def parse_integer(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return int(float(stripped.replace(",", "")))


def normalize_tree_text(text: str) -> str:
    """Normalize common pasted tree text before parsing."""
    if "\\n" in text:
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _depth_from_marker_prefix(indent: str) -> int:
    """Infer tree depth from the characters before a tree branch marker."""
    expanded = indent.expandtabs(4)
    if not expanded:
        return 1

    # Common tree printers reserve four columns for each ancestor level:
    # spaces, "│   ", "|   ", and similar vertical guide variants.
    depth = 1
    index = 0
    while index < len(expanded):
        char = expanded[index]
        if char in " │|┃":
            depth += 1
            index += 4 if index + 4 <= len(expanded) else 1
        else:
            index += 1
    return depth


def clean_tree_name(raw_line: str) -> tuple[int, str]:
    """Return tree depth and node text from a common CLI-style tree line."""
    line = raw_line.rstrip()
    marker_match = TREE_MARKER_RE.match(line)
    if marker_match:
        return (
            _depth_from_marker_prefix(marker_match.group("indent")),
            marker_match.group("content").strip(),
        )

    prefix_chars = set(" │├└─┬┼╰╭╮╯┃┣┗━+`|\\")
    index = 0
    while index < len(line) and line[index] in prefix_chars:
        index += 1

    prefix = line[:index]
    content = line[index:].strip()

    if prefix:
        depth = max(0, len(prefix.replace("─", "")) // 4)
        if "├" in prefix or "└" in prefix or "+" in prefix or "`" in prefix:
            depth += 1
        return depth, content

    leading_spaces = len(line) - len(line.lstrip(" "))
    return leading_spaces // 4, content


def split_name_and_size(content: str) -> tuple[str, int | None]:
    patterns = [
        r"^(?P<name>.+?)\s*[\(\[]\s*(?P<size>[\d,.]+)\s*(?P<unit>bytes?|b|[kmgt]i?b)\s*[\)\]]\s*$",
        r"^(?P<name>.+?)\s{2,}(?P<size>[\d,.]+)\s*(?P<unit>bytes?|b|[kmgt]i?b)\s*$",
        r"^(?P<name>.+?)\s+-\s+(?P<size>[\d,.]+)\s*(?P<unit>bytes?|b|[kmgt]i?b)\s*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, content, flags=re.IGNORECASE)
        if match:
            size = parse_size(match.group("size"), match.group("unit"))
            return match.group("name").strip(), size
    return content.strip(), None


def _normalize_header(value: str) -> str:
    return value.strip().lstrip("\ufeff").lower().replace(" ", "")


def _csv_column(fieldnames: list[str], candidates: set[str]) -> str | None:
    for fieldname in fieldnames:
        if _normalize_header(fieldname) in candidates:
            return fieldname
    return None


def is_cold_page_csv_text(text: str) -> bool:
    """Return True when text looks like the cold-page CSV export format."""
    for line in normalize_tree_text(text).splitlines():
        if not line.strip():
            continue
        columns = next(reader(StringIO(line)), [])
        normalized = {_normalize_header(column) for column in columns}
        return bool(
            {"名称", "name"} & normalized
            and ({"冷页数", "coldpages"} & normalized)
            and ({"内存大小(kb)", "memorysize(kb)", "size(kb)"} & normalized)
        )
    return False


def _csv_name_to_segments(name: str) -> list[str]:
    """Split file-path plus optional code-package suffix into hierarchy segments."""
    path_part, separator, package_part = name.strip().partition(":")
    path_segments = [segment for segment in path_part.strip("/").split("/") if segment]
    if not path_segments and path_part.strip():
        path_segments = [path_part.strip()]

    package_segments: list[str] = []
    if separator:
        package_segments = [segment for segment in package_part.split(".") if segment]

    return path_segments + package_segments


def parse_cold_page_csv_text(text: str, root_name: str = "SceneBoard.hap") -> TreeNode:
    """Parse cold-page CSV rows into a tree.

    The CSV format uses a file path in the first column, optionally followed by a
    colon and dot-separated package hierarchy, for example
    ``ets/modules.abc:ohos.launchercommon.src``.
    """
    normalized_text = normalize_tree_text(text)
    reader = DictReader(StringIO(normalized_text))
    fieldnames = reader.fieldnames or []
    name_column = _csv_column(fieldnames, {"名称", "name"})
    pages_column = _csv_column(fieldnames, {"冷页数", "coldpages"})
    size_column = _csv_column(
        fieldnames, {"内存大小(kb)", "memorysize(kb)", "size(kb)"}
    )
    if not (name_column and pages_column and size_column):
        raise ValueError("CSV 缺少 名称、冷页数 或 内存大小 (KB) 列。")

    root = TreeNode(root_name, root_name)
    nodes: dict[str, TreeNode] = {root.path: root}
    seen_rows: set[tuple[str, int | None, int | None]] = set()

    for row in reader:
        raw_name = (row.get(name_column) or "").strip()
        if not raw_name or _normalize_header(raw_name) in {"名称", "name"}:
            continue

        size_kb = parse_integer(row.get(size_column))
        cold_pages = parse_integer(row.get(pages_column))
        size_bytes = size_kb * 1024 if size_kb is not None else None
        row_identity = (raw_name, cold_pages, size_bytes)
        if row_identity in seen_rows:
            continue
        seen_rows.add(row_identity)

        segments = _csv_name_to_segments(raw_name)
        if not segments:
            continue

        parent = root
        for segment in segments:
            path = f"{parent.path}/{segment}"
            node = nodes.get(path)
            if node is None:
                node = TreeNode(segment, path, parent=parent)
                parent.children.append(node)
                nodes[path] = node
            parent = node

        if parent.explicit_size is None:
            parent.explicit_size = size_bytes
        if parent.cold_pages is None:
            parent.cold_pages = cold_pages

    return root


def parse_tree_text(text: str) -> TreeNode:
    if is_cold_page_csv_text(text):
        return parse_cold_page_csv_text(text)

    root = TreeNode("root", "")
    stack: list[TreeNode] = [root]

    for raw_line in normalize_tree_text(text).splitlines():
        if not raw_line.strip():
            continue
        depth, content = clean_tree_name(raw_line)
        if not content:
            continue
        name, explicit_size = split_name_and_size(content)
        is_directory_hint = name.endswith("/") or explicit_size is None
        display_name = name.rstrip("/") if is_directory_hint else name

        while len(stack) > depth + 1:
            stack.pop()

        parent = stack[-1]
        path = f"{parent.path}/{display_name}" if parent.path else display_name
        node = TreeNode(display_name, path, explicit_size, parent=parent)
        parent.children.append(node)

        if is_directory_hint:
            stack.append(node)

    if len(root.children) == 1 and root.children[0].explicit_size is None:
        only_child = root.children[0]
        only_child.parent = None
        return only_child
    return root


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def flatten_tree(node: TreeNode) -> list[dict[str, object]]:
    rows = []

    def visit(current: TreeNode) -> None:
        total = current.total_size()
        rows.append(
            {
                "name": current.name,
                "path": current.path,
                "parent": current.parent.path if current.parent else "",
                "size_bytes": total,
                "size_label": human_size(total),
                "kind": "File" if current.is_file else "Folder",
                "children": len(current.children),
                "cold_pages": current.cold_pages,
            }
        )
        for child in current.children:
            visit(child)

    visit(node)
    return rows


def iter_files(node: TreeNode) -> Iterable[TreeNode]:
    if node.is_file:
        yield node
    for child in node.children:
        yield from iter_files(child)
