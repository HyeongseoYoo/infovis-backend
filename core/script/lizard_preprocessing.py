#!/usr/bin/env python3

import csv
import json
from pathlib import Path

def normalize_file_path(path_str: str) -> str:
    """
    Lizard는 경로를 './src/foo.c' 처럼 찍으므로
    './' prefix 제거해서 'src/foo.c' 로 바꿔준다.
    """
    if path_str.startswith("./"):
        return path_str[2:]
    return path_str


def main():
    repo_root = Path.cwd() 
    inp = repo_root / "lizard_result.csv"
    outp = repo_root / "lizard_result.json"

    print(f"[lizard_preprocessing] input  = {inp}")
    print(f"[lizard_preprocessing] output = {outp}")

    if not inp.is_file():
        raise FileNotFoundError(f"lizard_result.csv not found at {inp}")

    results = []
    with inp.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            # 빈 줄이나 컬럼 수 안 맞으면 스킵
            if not row or len(row) < 11:
                continue

            try:
                nloc = int(row[0])
                ccn = int(row[1])
                param_count = int(row[3])
                length = int(row[4])
                file_path = normalize_file_path(row[6])
                func_name = row[7]
                start_line = int(row[9])
                end_line = int(row[10])
            except ValueError:
                # 숫자 파싱 실패하는 헤더/이상행 등은 스킵
                continue

            rec = {
                "NLOC": nloc,
                "CCN": ccn,
                "param": param_count,
                "length": length,
                "file": file_path,
                "function": func_name,
                "start_line": start_line,
                "end_line": end_line,
            }
            results.append(rec)

    with outp.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[lizard_preprocessing] Wrote {outp}: {len(results)} functions.")


if __name__ == "__main__":
    main()
