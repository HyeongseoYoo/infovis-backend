#!/usr/bin/env python3

import json
from pathlib import Path
from collections import defaultdict


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_functions_by_file(lizard_funcs):

    by_file = defaultdict(list)
    for func in lizard_funcs:
        file_ = func.get("file")
        if not file_:
            continue
        by_file[file_].append(func)

    # 각 파일별로 start_line 기준으로 정렬해 두면 탐색이 조금 더 직관적
    for file_, funcs in by_file.items():
        funcs.sort(key=lambda f: f.get("start_line", 0))

    return by_file


def find_function_for_warning(warning, funcs_in_file):
    line = warning.get("line")
    if line is None:
        return None

    for func in funcs_in_file:
        start = func.get("start_line")
        end = func.get("end_line")
        if start is None or end is None:
            continue
        if start <= line <= end:
            return func

    return None


def main():
    repo_root = Path.cwd()

    cpplint_path = repo_root / "cpplint_result.json"
    lizard_path = repo_root / "lizard_result.json"
    out_path = repo_root / "cpplint_with_funcs.json"

    print(f"[cpplint_attach_function] cpplint input = {cpplint_path}")
    print(f"[cpplint_attach_function] lizard input  = {lizard_path}")
    print(f"[cpplint_attach_function] output       = {out_path}")

    if not cpplint_path.is_file():
        raise FileNotFoundError(f"cpplint_result.json not found at {cpplint_path}")
    if not lizard_path.is_file():
        raise FileNotFoundError(f"lizard_result.json not found at {lizard_path}")

    cpplint_data = load_json(cpplint_path)
    lizard_data = load_json(lizard_path)

    # file -> [functions ...]
    funcs_by_file = build_functions_by_file(lizard_data)

    matched_warnings = []

    for w in cpplint_data:
        file_ = w.get("file")
        if not file_:
            continue

        funcs_in_file = funcs_by_file.get(file_, [])
        if not funcs_in_file:
            continue

        func_rec = find_function_for_warning(w, funcs_in_file)
        if func_rec is None:
            continue  # 매칭 실패 → 버림

        # 원래 warning 필드를 복사하고, lizard function 필드를 추가
        w2 = dict(w)
        w2["function"] = func_rec.get("function")

        matched_warnings.append(w2)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(matched_warnings, f, indent=2, ensure_ascii=False)

    print(
        f"[cpplint_attach_function] Wrote {out_path}: "
        f"{len(matched_warnings)} warnings (matched)."
    )


if __name__ == "__main__":
    main()
