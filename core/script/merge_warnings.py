#!/usr/bin/env python3

import json
from pathlib import Path


def load_json_if_exists(path: Path):
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_id(rec: dict) -> str:
    file_ = rec.get("file", "") or ""
    func = rec.get("function", "") or ""
    line = rec.get("line", "")
    warning = rec.get("warning", "") or ""

    # line 이 None 이거나 숫자가 아닐 수도 있으니 문자열로 강제 변환
    try:
        line_str = str(int(line))
    except (TypeError, ValueError):
        line_str = str(line)

    return f"{file_}@{func}@{line_str}@{warning}"


def main():
    repo_root = Path.cwd()

    cpplint_path = repo_root / "cpplint_with_funcs.json"
    infer_path = repo_root / "infer_result.json"
    out_path = repo_root / "warnings.json"

    print(f"[merge_warnings] cpplint input = {cpplint_path}")
    print(f"[merge_warnings] infer   input = {infer_path}")
    print(f"[merge_warnings] output       = {out_path}")

    cpplint_data = load_json_if_exists(cpplint_path)
    infer_data = load_json_if_exists(infer_path)

    merged = []
    seen_ids = set()

    # 1) cpplint 경고 먼저 처리
    for rec in cpplint_data:
        rid = build_id(rec)
        if rid in seen_ids:
            continue
        rec_with_id = dict(rec)
        rec_with_id["id"] = rid
        merged.append(rec_with_id)
        seen_ids.add(rid)

    # 2) infer 경고 처리
    for rec in infer_data:
        rid = build_id(rec)
        if rid in seen_ids:
            continue
        rec_with_id = dict(rec)
        rec_with_id["id"] = rid
        merged.append(rec_with_id)
        seen_ids.add(rid)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"[merge_warnings] Wrote {out_path}: {len(merged)} warnings (unique by id).")


if __name__ == "__main__":
    main()
