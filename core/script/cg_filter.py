#!/usr/bin/env python3

import json
from pathlib import Path
from collections import defaultdict


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    repo_root = Path.cwd()
    cg_path = repo_root / "cg.json"
    lizard_path = repo_root / "lizard_result.json"
    out_path = repo_root / "cg_filtered.json"

    print(f"[cg_filter_by_lizard] cg input      = {cg_path}")
    print(f"[cg_filter_by_lizard] lizard input  = {lizard_path}")
    print(f"[cg_filter_by_lizard] cg output     = {out_path}")

    if not cg_path.is_file():
        raise FileNotFoundError(f"cg.json not found at {cg_path}")
    if not lizard_path.is_file():
        raise FileNotFoundError(f"lizard_result.json not found at {lizard_path}")

    cg_data = load_json(cg_path)
    lizard_data = load_json(lizard_path)

    nodes = cg_data.get("nodes", [])
    edges = cg_data.get("edges", [])

    # 1) lizard_result.json 에서 function -> (file, start_line, end_line) 매핑 만들기
    func_map = {}
    for rec in lizard_data:
        func_name = rec.get("function")
        if not func_name:
            continue
        # 동일한 function 이름이 여러 파일에 있을 수도 있지만,
        # 여기서는 일단 첫 번째 걸 쓰거나 덮어써도 됨.
        func_map[func_name] = {
            "file": rec.get("file"),
            "start_line": rec.get("start_line"),
            "end_line": rec.get("end_line"),
        }

    # 2) node 필터링 + file 정보 붙이기
    filtered_nodes = []
    allowed_ids = set()

    for node in nodes:
        name = node.get("name") or node.get("id")
        if name in func_map:
            info = func_map[name]
            node_with_file = dict(node)
            node_with_file["file"] = info.get("file")
            node_with_file["start_line"] = info.get("start_line")
            node_with_file["end_line"] = info.get("end_line")
            filtered_nodes.append(node_with_file)
            allowed_ids.add(node_with_file["id"])

    # 3) edges 도 허용된 노드만 남기기
    filtered_edges = []
    for e in edges:
        s = e.get("source")
        t = e.get("target")
        if s in allowed_ids and t in allowed_ids:
            filtered_edges.append(e)

    # 4) degree 재계산
    out_deg = defaultdict(int)
    in_deg = defaultdict(int)

    for e in filtered_edges:
        s = e["source"]
        t = e["target"]
        out_deg[s] += 1
        in_deg[t] += 1

    for n in filtered_nodes:
        nid = n["id"]
        indeg = in_deg.get(nid, 0)
        outdeg = out_deg.get(nid, 0)
        n["in_degree"] = indeg
        n["out_degree"] = outdeg
        n["degree"] = indeg + outdeg

    result = {
        "nodes": filtered_nodes,
        "edges": filtered_edges,
    }

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(
        f"[cg_filter_by_lizard] Wrote {out_path}: "
        f"{len(filtered_nodes)} nodes, {len(filtered_edges)} edges."
    )


if __name__ == "__main__":
    main()
