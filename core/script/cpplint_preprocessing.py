#!/usr/bin/env python3

import re
import json
from pathlib import Path


LINE_RE = re.compile(
    r"""
    ^(?P<file>.+?)              # 파일 경로
    :(?P<line>\d+)              # 라인 번호
    :\s*                        # 콜론 뒤 공백들
    (?P<detail>.*?)             # 경고 메시지 본문 (lazy)
    \s*\[                       # 첫 번째 대괄호 시작
    (?P<category>[^/\]]+)       # 카테고리 (슬래시 전까지)
    /(?P<warning>[^\]]+)        # warning 이름 (']' 전까지)
    \]\s*                       # 첫 번째 닫는 대괄호
    (?:\[\d+\]\s*)?             # 마지막 [숫자] 부분은 있어도 되고 없어도 됨
    $
    """,
    re.VERBOSE,
)


def normalize_file_path(path_str: str, repo_root: Path) -> str:
    """
    절대 경로로 나온 cpplint file 을 repo_root 기준 상대 경로로 바꿔줌.
    예: /tmp/analysis_4/build/... -> build/...
    """
    p = Path(path_str)
    try:
        rel = p.relative_to(repo_root)
        return str(rel)
    except ValueError:
        # repo_root 바깥이면 그냥 원래 문자열 반환
        return path_str


def parse_cpplint_line(line: str, repo_root: Path):
    line = line.rstrip("\n")
    if not line.strip():
        return None

    m = LINE_RE.match(line)
    if not m:
        # 포맷 안 맞는 라인은 스킵하거나, 필요하면 로그에 남길 수 있음
        return None

    file_raw = m.group("file")
    line_no = int(m.group("line"))
    detail = m.group("detail").strip()
    category = m.group("category").strip()
    warning = m.group("warning").strip()

    file_norm = normalize_file_path(file_raw, repo_root)

    return {
        "file": file_norm,
        "line": line_no,
        "detail": detail,
        "category": category,
        "warning": warning,
        # 추가 필드들
        "severity_level": "LOW",
        "tool": "cpplint",
        "severity": "style",
        "column": None,
    }


def main():
    repo_root = Path.cwd()                  # Celery에서 cwd=repo_dir 로 실행된다고 가정
    inp = repo_root / "cpplint_result.txt"
    outp = repo_root / "cpplint_result.json"

    if not inp.is_file():
        raise FileNotFoundError(f"cpplint_result.txt not found at {inp}")

    results = []
    with inp.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            rec = parse_cpplint_line(raw, repo_root)
            if rec is not None:
                results.append(rec)

    with outp.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"[cpplint_preprocessing] Wrote {outp}: {len(results)} records.")


if __name__ == "__main__":
    main()
