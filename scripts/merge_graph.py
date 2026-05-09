"""Merge and deduplicate knowledge graph nodes. Build cross-document connections."""

import json
import os
import re
import sys
from difflib import SequenceMatcher

SIMILARITY_THRESHOLD = 0.75


def title_similarity(a: str, b: str) -> float:
    """Calculate similarity between two titles."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def normalize_id(title: str) -> str:
    """Create a clean ID from a title string."""
    # Remove special chars, convert to lowercase kebab
    id_str = re.sub(r"[^\w\s-]", "", title.lower())
    id_str = re.sub(r"\s+", "-", id_str.strip())
    return id_str


def merge_similar_nodes(nodes: list[dict]) -> list[dict]:
    """Find and merge nodes that refer to the same concept.

    When merging, keep the more detailed summary and combine tags.
    """
    merged = []
    skip_indices = set()

    for i, node_i in enumerate(nodes):
        if i in skip_indices:
            continue

        merged_node = dict(node_i)
        merged_node["aliases"] = [node_i["title"]]

        for j, node_j in enumerate(nodes):
            if j <= i or j in skip_indices:
                continue
            sim = title_similarity(node_i["title"], node_j["title"])
            if sim >= SIMILARITY_THRESHOLD:
                # Merge: keep longer summary, combine tags
                if len(node_j.get("summary", "")) > len(merged_node.get("summary", "")):
                    merged_node["summary"] = node_j["summary"]
                merged_node["tags"] = list(set(
                    node_i.get("tags", []) + node_j.get("tags", [])
                ))
                merged_node["aliases"].append(node_j["title"])
                merged_node["importance"] = max(
                    node_i.get("importance", 1), node_j.get("importance", 1)
                )
                skip_indices.add(j)

        merged.append(merged_node)

    # Update IDs to be clean
    for node in merged:
        node["id"] = normalize_id(node["title"])

    return merged


def build_global_relations(nodes: list[dict], existing_edges: list[dict]) -> list[dict]:
    """Add inferred global relations based on shared tags and title similarity.

    Also normalizes edge IDs to match merged node IDs.
    """
    # Build a lookup from old id → new id
    id_map = {}
    for node in nodes:
        title_normalized = normalize_id(node["title"])
        id_map[node["id"]] = title_normalized
        for alias in node.get("aliases", []):
            id_map[normalize_id(alias)] = title_normalized

    new_edges = []
    seen_edge_keys = set()

    # Normalize existing edges
    for edge in existing_edges:
        from_id = id_map.get(edge["from"], edge["from"])
        to_id = id_map.get(edge["to"], edge["to"])
        if from_id == to_id:
            continue
        edge_key = f"{from_id}|{edge['type']}|{to_id}"
        if edge_key not in seen_edge_keys:
            edge["from"] = from_id
            edge["to"] = to_id
            new_edges.append(edge)
            seen_edge_keys.add(edge_key)

    # Infer additional cross-document relations by tag overlap
    node_by_id = {n["id"]: n for n in nodes}

    for i, ni in enumerate(nodes):
        for j, nj in enumerate(nodes):
            if j <= i:
                continue
            # Check shared tags
            tags_i = set(ni.get("tags", []))
            tags_j = set(nj.get("tags", []))
            shared = tags_i & tags_j

            if len(shared) >= 2:
                edge_key = f"{ni['id']}|related|{nj['id']}"
                reverse_key = f"{nj['id']}|related|{ni['id']}"
                if edge_key not in seen_edge_keys and reverse_key not in seen_edge_keys:
                    new_edges.append({
                        "from": ni["id"],
                        "to": nj["id"],
                        "type": "related",
                        "description": f"共享标签: {', '.join(sorted(shared)[:3])}",
                    })
                    seen_edge_keys.add(edge_key)

    return new_edges


def build_tree_structure(nodes: list[dict]) -> list[dict]:
    """Organize nodes into a tree hierarchy for the mind map.

    Strategy:
    1. Group nodes by tags to form top-level categories
    2. Use parentId relationships where available
    3. Fill in missing parents with auto-grouping by tag
    """
    return nodes  # Keep flat structure; parentId is already set during extraction


def merge_graph(input_path: str, output_path: str):
    """Main merge function."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    print(f"Input: {len(nodes)} nodes, {len(edges)} edges")

    # Step 1: Merge similar nodes
    nodes = merge_similar_nodes(nodes)
    print(f"After dedup: {len(nodes)} nodes")

    # Step 2: Rebuild edges with normalized IDs and infer new relations
    edges = build_global_relations(nodes, edges)
    print(f"After edge normalization + inference: {len(edges)} edges")

    # Step 3: Build tree structure
    nodes = build_tree_structure(nodes)

    result = {"nodes": nodes, "edges": edges}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nMerged graph → {output_path}")
    return result


if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "../output/extracted_knowledge.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "../output/knowledge-data.json"
    merge_graph(input_file, output_file)
