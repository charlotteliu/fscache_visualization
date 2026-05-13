from __future__ import annotations

import re
from dataclasses import dataclass, field
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


@dataclass
class TreeNode:
    name: str
    path: str
    explicit_size: int | None = None
    children: list["TreeNode"] = field(default_factory=list)
    parent: "TreeNode | None" = None

    @property
    def is_file(self) -> bool:
        return not self.children and self.explicit_size is not None

    def total_size(self) -> int:
        if self.children:
            return sum(child.total_size() for child in self.children)
        return self.explicit_size or 0


def parse_size(value: str | None, unit: str | None) -> int | None:
    if value is None or unit is None:
        return None
    normalized_unit = unit.lower()
    multiplier = SIZE_UNITS.get(normalized_unit)
    if multiplier is None:
        return None
    return int(float(value.replace(",", "")) * multiplier)


def clean_tree_name(raw_line: str) -> tuple[int, str]:
    """Return tree depth and node text from a common CLI-style tree line."""
    prefix_chars = set(" │├└─┬┼╰╭╮╯┃┣┗━+`|\\")
    index = 0
    while index < len(raw_line) and raw_line[index] in prefix_chars:
        index += 1

    prefix = raw_line[:index]
    content = raw_line[index:].strip()

    if prefix:
        depth = max(0, len(prefix.replace("─", "")) // 4)
        if "├" in prefix or "└" in prefix or "+" in prefix or "`" in prefix:
            depth += 1
        return depth, content

    leading_spaces = len(raw_line) - len(raw_line.lstrip(" "))
    return leading_spaces // 4, content


def split_name_and_size(content: str) -> tuple[str, int | None]:
    patterns = [
        r"^(?P<name>.+?)\s*[\(\[]\s*(?P<size>[\d,.]+)\s*(?P<unit>bytes?|[kmgt]i?b)\s*[\)\]]\s*$",
        r"^(?P<name>.+?)\s{2,}(?P<size>[\d,.]+)\s*(?P<unit>bytes?|[kmgt]i?b)\s*$",
        r"^(?P<name>.+?)\s+-\s+(?P<size>[\d,.]+)\s*(?P<unit>bytes?|[kmgt]i?b)\s*$",
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

    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        depth, content = clean_tree_name(raw_line.rstrip())
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
