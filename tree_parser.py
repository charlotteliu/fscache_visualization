from __future__ import annotations

import csv
import re
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
    children: list["TreeNode"] = field(default_factory=list)
    parent: "TreeNode | None" = None
    explicit_cold_pages: int | None = None
    kind: str | None = None

    @property
    def is_file(self) -> bool:
        return not self.children and self.explicit_size is not None

    def total_size(self) -> int:
        if self.explicit_size is not None:
            return self.explicit_size
        if self.children:
            return sum(child.total_size() for child in self.children)
        return 0

    def total_cold_pages(self) -> int:
        if self.explicit_cold_pages is not None:
            return self.explicit_cold_pages
        if self.children:
            return sum(child.total_cold_pages() for child in self.children)
        return 0

    def display_kind(self) -> str:
        if self.kind:
            return self.kind
        return "File" if self.is_file else "Folder"


def parse_size(value: str | None, unit: str | None) -> int | None:
    if value is None or unit is None:
        return None
    normalized_unit = unit.lower()
    multiplier = SIZE_UNITS.get(normalized_unit)
    if multiplier is None:
        return None
    return int(float(value.replace(",", "")) * multiplier)


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


def parse_tree_text(text: str) -> TreeNode:
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


def _parse_number(value: str | None, *, allow_float: bool = False) -> int | None:
    if value is None:
        return None
    normalized = value.strip().replace(",", "")
    if not normalized:
        return None
    try:
        parsed = float(normalized) if allow_float else int(normalized)
    except ValueError:
        return None
    return int(parsed)


def _csv_header_indices(header: list[str]) -> tuple[int, int, int]:
    normalized = [column.strip().lower() for column in header]
    name_index = next(
        (
            index
            for index, column in enumerate(normalized)
            if column in {"名称", "name", "path", "文件", "文件名"}
        ),
        0,
    )
    cold_index = next(
        (
            index
            for index, column in enumerate(normalized)
            if "冷页" in column or "cold" in column
        ),
        1,
    )
    size_index = next(
        (
            index
            for index, column in enumerate(normalized)
            if "内存" in column
            or "kb" in column
            or "size" in column
            or "memory" in column
        ),
        2,
    )
    return name_index, cold_index, size_index


def _ensure_child(parent: TreeNode, name: str, kind: str) -> TreeNode:
    path = f"{parent.path}/{name}" if parent.path else name
    for child in parent.children:
        if child.path == path:
            if child.kind in {None, "File"} and kind != "File":
                child.kind = kind
            return child
    child = TreeNode(name=name, path=path, parent=parent, kind=kind)
    parent.children.append(child)
    return child


def parse_cold_page_csv(text: str) -> TreeNode:
    """Parse cold-page CSV into a file/package/class hierarchy.

    Expected columns are ``名称,冷页数,内存大小 (KB)``. Names before ``:`` are
    slash-separated file paths; names after ``:`` are dot-separated package and
    class paths, so ``ets/modules.abc:hms-ai.utils.JsonUtil`` expands to
    ``ets -> modules.abc -> hms-ai -> utils -> JsonUtil``.
    """
    normalized_text = normalize_tree_text(text).strip("\ufeff\n ")
    reader = csv.reader(StringIO(normalized_text))
    rows = [row for row in reader if row and any(cell.strip() for cell in row)]
    if not rows:
        return TreeNode("root", "")

    name_index, cold_index, size_index = _csv_header_indices(rows[0])
    root = TreeNode("root", "", kind="Root")

    for row in rows[1:]:
        if len(row) <= name_index:
            continue
        raw_name = row[name_index].strip()
        if not raw_name or raw_name == rows[0][name_index].strip():
            continue

        cold_pages = _parse_number(row[cold_index] if len(row) > cold_index else None)
        memory_kb = _parse_number(
            row[size_index] if len(row) > size_index else None,
            allow_float=True,
        )
        size_bytes = memory_kb * 1024 if memory_kb is not None else None
        if cold_pages is None and size_bytes is None:
            continue

        file_path, separator, symbol_path = raw_name.partition(":")
        file_parts = [part for part in file_path.split("/") if part]
        symbol_parts = (
            [part for part in symbol_path.split(".") if part] if separator else []
        )
        parts = file_parts + symbol_parts
        if not parts:
            continue

        current = root
        for index, part in enumerate(parts):
            if index < len(file_parts) - 1:
                kind = "Folder"
            elif index == len(file_parts) - 1:
                kind = "ABC File" if symbol_parts else "File"
            elif index == len(parts) - 1:
                kind = "Class"
            else:
                kind = "Package"
            current = _ensure_child(current, part, kind)

        current.explicit_cold_pages = cold_pages
        current.explicit_size = size_bytes
        if symbol_parts:
            current.path = f"{file_path}:{'.'.join(symbol_parts)}"
            current.name = symbol_parts[-1]

    if len(root.children) == 1:
        only_child = root.children[0]
        only_child.parent = None
        return only_child
    return root


def looks_like_cold_page_csv(text: str) -> bool:
    first_line = normalize_tree_text(text).lstrip("\ufeff\n ").splitlines()[0:1]
    if not first_line:
        return False
    columns = [column.strip().lower() for column in next(csv.reader(first_line))]
    return any(column in {"名称", "name"} for column in columns) and (
        any("冷页" in column or "cold" in column for column in columns)
        or any("内存" in column or "memory" in column for column in columns)
    )


def parse_input_text(text: str, input_format: str = "auto") -> TreeNode:
    if input_format == "cold_page_csv" or (
        input_format == "auto" and looks_like_cold_page_csv(text)
    ):
        return parse_cold_page_csv(text)
    return parse_tree_text(text)


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
        cold_pages = current.total_cold_pages()
        rows.append(
            {
                "name": current.name,
                "path": current.path,
                "parent": current.parent.path if current.parent else "",
                "size_bytes": total,
                "size_kb": total // 1024,
                "size_label": human_size(total),
                "cold_pages": cold_pages,
                "kind": current.display_kind(),
                "children": len(current.children),
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
