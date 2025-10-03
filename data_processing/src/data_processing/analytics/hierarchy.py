"""Build hierarchical structures from data."""
from typing import Dict, List, Optional, Any
import polars as pl
from collections import defaultdict


class HierarchyNode:
    """Represents a node in a hierarchy."""

    def __init__(self, id: str, data: Dict[str, Any], parent: Optional['HierarchyNode'] = None):
        self.id = id
        self.data = data
        self.parent = parent
        self.children: List[HierarchyNode] = []
        self.level = 0 if parent is None else parent.level + 1

    def add_child(self, child: 'HierarchyNode') -> None:
        """Add a child node."""
        child.parent = self
        child.level = self.level + 1
        self.children.append(child)

    def get_path(self) -> List[str]:
        """Get path from root to this node."""
        path = []
        node = self
        while node is not None:
            path.insert(0, node.id)
            node = node.parent
        return path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "data": self.data,
            "level": self.level,
            "children": [child.to_dict() for child in self.children],
        }


class HierarchyBuilder:
    """Builds hierarchical structures from flat data."""

    def __init__(self):
        self.root: Optional[HierarchyNode] = None
        self._nodes: Dict[str, HierarchyNode] = {}

    def build_from_parent_column(
        self,
        df: pl.DataFrame,
        id_column: str,
        parent_column: str,
        data_columns: Optional[List[str]] = None,
    ) -> HierarchyNode:
        """Build hierarchy from parent-child relationships.

        Args:
            df: Input DataFrame
            id_column: Column containing node IDs
            parent_column: Column containing parent IDs
            data_columns: Additional columns to include in node data

        Returns:
            Root node of hierarchy
        """
        self._nodes.clear()

        # Determine data columns
        if data_columns is None:
            data_columns = [col for col in df.columns if col not in [id_column, parent_column]]

        # Create nodes
        for row in df.iter_rows(named=True):
            node_id = str(row[id_column])
            node_data = {col: row[col] for col in data_columns}
            node = HierarchyNode(node_id, node_data)
            self._nodes[node_id] = node

        # Build relationships
        root_nodes = []
        for row in df.iter_rows(named=True):
            node_id = str(row[id_column])
            parent_id = row[parent_column]

            node = self._nodes[node_id]

            if parent_id is None or parent_id == "":
                root_nodes.append(node)
            else:
                parent_id_str = str(parent_id)
                if parent_id_str in self._nodes:
                    parent_node = self._nodes[parent_id_str]
                    parent_node.add_child(node)

        # Handle multiple roots by creating virtual root
        if len(root_nodes) > 1:
            virtual_root = HierarchyNode("__root__", {"name": "Root"})
            for root_node in root_nodes:
                virtual_root.add_child(root_node)
            self.root = virtual_root
        elif len(root_nodes) == 1:
            self.root = root_nodes[0]
        else:
            raise ValueError("No root nodes found in hierarchy")

        return self.root

    def build_from_path(
        self,
        df: pl.DataFrame,
        path_column: str,
        separator: str = "/",
        data_columns: Optional[List[str]] = None,
    ) -> HierarchyNode:
        """Build hierarchy from path strings.

        Args:
            df: Input DataFrame
            path_column: Column containing path strings (e.g., "a/b/c")
            separator: Path separator
            data_columns: Additional columns to include in node data

        Returns:
            Root node of hierarchy
        """
        self._nodes.clear()

        # Create virtual root
        self.root = HierarchyNode("__root__", {"name": "Root"})
        self._nodes["__root__"] = self.root

        # Determine data columns
        if data_columns is None:
            data_columns = [col for col in df.columns if col != path_column]

        # Process each path
        for row in df.iter_rows(named=True):
            path = row[path_column]
            if not path:
                continue

            parts = path.split(separator)
            current_path = []
            parent_node = self.root

            for part in parts:
                if not part:
                    continue

                current_path.append(part)
                node_id = separator.join(current_path)

                # Create node if it doesn't exist
                if node_id not in self._nodes:
                    node_data = {"name": part}
                    node = HierarchyNode(node_id, node_data)
                    self._nodes[node_id] = node
                    parent_node.add_child(node)
                else:
                    node = self._nodes[node_id]

                parent_node = node

            # Add data to leaf node
            if data_columns:
                for col in data_columns:
                    parent_node.data[col] = row[col]

        return self.root

    def get_node(self, node_id: str) -> Optional[HierarchyNode]:
        """Get node by ID."""
        return self._nodes.get(node_id)

    def get_level(self, level: int) -> List[HierarchyNode]:
        """Get all nodes at a specific level."""
        nodes = []
        for node in self._nodes.values():
            if node.level == level:
                nodes.append(node)
        return nodes

    def get_depth(self) -> int:
        """Get maximum depth of hierarchy."""
        if not self.root:
            return 0
        return max(node.level for node in self._nodes.values())

    def get_leaf_nodes(self) -> List[HierarchyNode]:
        """Get all leaf nodes."""
        return [node for node in self._nodes.values() if not node.children]

    def to_flat_dataframe(self) -> pl.DataFrame:
        """Convert hierarchy back to flat DataFrame."""
        records = []

        for node in self._nodes.values():
            if node.id == "__root__":
                continue

            record = {
                "id": node.id,
                "level": node.level,
                "path": "/".join(node.get_path()[1:]),  # Exclude root
                "parent_id": node.parent.id if node.parent and node.parent.id != "__root__" else None,
                "num_children": len(node.children),
                **node.data,
            }
            records.append(record)

        return pl.DataFrame(records)

    def print_tree(self, node: Optional[HierarchyNode] = None, indent: int = 0) -> None:
        """Print tree structure.

        Args:
            node: Node to start from (uses root if None)
            indent: Indentation level
        """
        if node is None:
            node = self.root

        if node is None:
            return

        prefix = "  " * indent
        name = node.data.get("name", node.id)
        print(f"{prefix}└─ {name} (id={node.id}, level={node.level}, children={len(node.children)})")

        for child in node.children:
            self.print_tree(child, indent + 1)
