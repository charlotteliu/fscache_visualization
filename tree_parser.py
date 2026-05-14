from __future__ import annotations

import csv
import io
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

TREE_MARKER_RE = re.compile(
    r"(?P<indent>.*?)(?P<marker>├──|└──|┣━━|┗━━|\+--|\|--|`--|╰──|╭──)"
    r"\s*(?P<content>.*)"
)
SOURCE_ROOT_MARKER = ("src", "main", "ets")


@dataclass
class TreeNode:
    name: str
    path: str
    explicit_size: int | None = None
    children: list["TreeNode"] = field(default_factory=list)
    parent: "TreeNode | None" = None
    kind: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_file(self) -> bool:
        return not self.children and self.explicit_size is not None

    @property
    def display_kind(self) -> str:
        if self.kind:
            return self.kind
        return "File" if self.is_file else "Folder"

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


def _strip_module_descriptor(module_name: str) -> str:
    descriptor = module_name.strip()
    if descriptor.startswith("L&"):
        descriptor = descriptor[2:]
    elif descriptor.startswith("L"):
        descriptor = descriptor[1:]
    descriptor = descriptor.rstrip(";")
    if "&" in descriptor:
        descriptor = descriptor.rsplit("&", 1)[0]
    return descriptor.strip("/")


def split_module_descriptor(module_name: str) -> tuple[str, list[str], str]:
    """Split an ArkTS module descriptor into module, package parts, and class name."""
    descriptor = _strip_module_descriptor(module_name)
    parts = [part for part in descriptor.split("/") if part]
    if not parts:
        return "unknown", [], module_name

    module_parts = parts[:2] if parts[0].startswith("@") and len(parts) >= 2 else parts[:1]
    module = "/".join(module_parts)
    remainder = parts[len(module_parts) :]

    source_index = -1
    for index in range(len(remainder) - len(SOURCE_ROOT_MARKER) + 1):
        if tuple(remainder[index : index + len(SOURCE_ROOT_MARKER)]) == SOURCE_ROOT_MARKER:
            source_index = index + len(SOURCE_ROOT_MARKER)
            break
    class_path_parts = remainder[source_index:] if source_index >= 0 else remainder

    if not class_path_parts:
        return module, [], module
    class_name = class_path_parts[-1]
    return module, class_path_parts[:-1], class_name


def _get_or_create_child(parent: TreeNode, name: str, kind: str) -> TreeNode:
    for child in parent.children:
        if child.name == name and child.kind == kind:
            return child
    path = f"{parent.path}/{name}" if parent.path else name
    child = TreeNode(name, path, parent=parent, kind=kind)
    parent.children.append(child)
    return child


def parse_module_csv_text(text: str) -> TreeNode:
    """Parse module_offset/module_name/total_method_size CSV into a module tree."""
    root = TreeNode("modules", "modules", kind="Root")
    normalized = normalize_tree_text(text).strip()
    reader = csv.DictReader(io.StringIO(normalized))

    for row in reader:
        raw_module_name = (row.get("module_name") or "").strip()
        if not raw_module_name:
            continue
        module_name, package_parts, class_name = split_module_descriptor(raw_module_name)
        size_value = (row.get("total_method_size") or "0").strip().replace(",", "")
        try:
            method_size = int(float(size_value))
        except ValueError:
            method_size = 0

        module_node = _get_or_create_child(root, module_name, "Module")
        parent = module_node
        for package_part in package_parts:
            parent = _get_or_create_child(parent, package_part, "Package")

        class_path = f"{parent.path}/{class_name}" if parent.path else class_name
        class_node = TreeNode(
            class_name,
            class_path,
            method_size,
            parent=parent,
            kind="Class",
            metadata={
                "module_offset": (row.get("module_offset") or "").strip(),
                "module_name": raw_module_name,
            },
        )
        parent.children.append(class_node)

    return root


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def human_count(value: int, unit: str = "B") -> str:
    display_value = float(value)
    for suffix in ["", "K", "M", "G", "T"]:
        if display_value < 1000 or suffix == "T":
            if suffix:
                return f"{display_value:.1f} {suffix}{unit}"
            return f"{int(display_value)} {unit}"
        display_value /= 1000
    return f"{display_value:.1f} T{unit}"


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
                "method_size_label": human_count(total, ""),
                "kind": current.display_kind,
                "children": len(current.children),
                "module_offset": current.metadata.get("module_offset", ""),
                "module_name": current.metadata.get("module_name", ""),
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
