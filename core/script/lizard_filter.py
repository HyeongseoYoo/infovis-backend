#!/usr/bin/env python3

import json
from pathlib import Path
from collections import defaultdict


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_cg_index(cg_nodes):

    index = {}
    for node in cg_nodes:
        file_ = node.get("file")
        func = node.get("name") or node.get("id")
        if not file_ or not func:
            continue

        key = (file_, func)
        index[key] = {
            "in_degree": node.get("in_degree", 0),
            "out_degree": node.get("out_degree", 0),
            "degree": node.get("degree", 0),
        }
    return index


def build_warning_stats(warnings):

    stats = defaultdict(lambda: {"HIGH": 0, "MID": 0, "LOW": 0})

    for w in warnings:
        file_ = w.get("file")
        func = w.get("function")
        sev = (w.get("severity_level") or "").upper()

        if not file_ or not func:
            continue

        key = (file_, func)

        if sev not in ("HIGH", "MID", "LOW"):
            sev = "LOW"

        stats[key][sev] += 1

    return stats


def main():
    repo_root = Path.cwd()

    lizard_path = repo_root / "lizard_result.json"
    cg_path = repo_root / "cg_filtered.json"
    warnings_path = repo_root / "warnings.json"
    out_path = repo_root / "functions.json"

    print(f"[build_functions] lizard input   = {lizard_path}")
    print(f"[build_functions] cg input       = {cg_path}")
    print(f"[build_functions] warnings input = {warnings_path}")
    print(f"[build_functions] output         = {out_path}")

    if not lizard_path.is_file():
        raise FileNotFoundError(f"lizard_result.json not found at {lizard_path}")
    if not cg_path.is_file():
        raise FileNotFoundError(f"cg_filtered.json not found at {cg_path}")
    if not warnings_path.is_file():
        raise FileNotFoundError(f"warnings.json not found at {warnings_path}")

    lizard_data = load_json(lizard_path)
    cg_data = load_json(cg_path)
    warnings_data = load_json(warnings_path)

    cg_nodes = cg_data.get("nodes", [])

    # 1) (file,function) -> degree 정보
    cg_index = build_cg_index(cg_nodes)

    # 2) (file,function) -> severity_level 별 warning 카운트
    warn_stats = build_warning_stats(warnings_data)

    functions = []

    # 3) lizard_result.json 을 돌면서
    #    cg_filtered 에 있는 (file,function) 만 남기고 degree/경고 통계 붙이기
    for rec in lizard_data:
        file_ = rec.get("file")
        func = rec.get("function")
        if not file_ or not func:
            continue

        key = (file_, func)

        # cg_filtered.json 에 없는 함수는 버린다
        if key not in cg_index:
            continue

        # 기본 function 정보 (lizard)
        func_rec = {
            "file": file_,
            "function": func,
            "NLOC": rec.get("NLOC"),
            "CCN": rec.get("CCN"),
            "param": rec.get("param"),
            "length": rec.get("length"),
            "start_line": rec.get("start_line"),
            "end_line": rec.get("end_line"),
        }

        # cg degree 정보 붙이기
        deg = cg_index[key]
        func_rec["in_degree"] = deg["in_degree"]
        func_rec["out_degree"] = deg["out_degree"]
        func_rec["degree"] = deg["degree"]

        # warning 통계 붙이기 (없으면 0으로 채운다)
        wstat = warn_stats.get(key, {"HIGH": 0, "MID": 0, "LOW": 0})
        func_rec["warning"] = {
            "HIGH": wstat.get("HIGH", 0),
            "MID": wstat.get("MID", 0),
            "LOW": wstat.get("LOW", 0),
        }

        functions.append(func_rec)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(functions, f, indent=2, ensure_ascii=False)

    print(f"[build_functions] Wrote {out_path}: {len(functions)} functions.")


if __name__ == "__main__":
    main()
