#!/usr/bin/env python3

import json
from pathlib import Path


def map_severity_level(severity: str) -> str:

    if not severity:
        return "LOW"
    s = severity.upper()
    if s == "ERROR":
        return "HIGH"
    if s == "WARNING":
        return "MID"
    if s in ("INFO", "ADVICE"):
        return "LOW"
    return "LOW"


def main():
    repo_root = Path.cwd()

    inp =  repo_root / "infer-out" / "report.json"
    outp = repo_root / "infer_result.json"

    if inp is None:
        raise FileNotFoundError("Cannot find infer report JSON.")

    
    print(f"[infer_preprocessing] input  = {inp}")
    print(f"[infer_preprocessing] output = {outp}")

    with inp.open("r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)

    # 데이터가 dict 하나일 수도 있고, list 일 수도 있어서 통일
    if isinstance(data, dict):
        records = [data]
    else:
        records = data

    results = []
    for item in records:
        # 안전하게 get 사용
        qualifier = item.get("qualifier", "")
        severity = item.get("severity", "")
        category = item.get("category", "")
        line = item.get("line")
        column = item.get("column")  # 없으면 None
        procedure = item.get("procedure", "")
        file_ = item.get("file", "")
        bug_type_hum = item.get("bug_type_hum", "")

        rec = {
            "detail": qualifier,
            "severity": severity,
            "category": category,
            "line": line,
            "column": column,
            "function": procedure,
            "file": file_,
            "warning": bug_type_hum,
            "severity_level": map_severity_level(severity),
            "tool": "infer",
        }
        results.append(rec)

    with outp.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[infer_preprocessing] Wrote {outp}: {len(results)} warnings.")


if __name__ == "__main__":
    main()
