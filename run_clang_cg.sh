#!/usr/bin/env bash
set -euo pipefail

# 0. 현재 디렉터리는 clone된 repo 루트라고 가정
# 1. compile_commands.json 찾기 (여기서는 루트에 있다고 가정)
COMPILE_DB="compile_commands.json"

if [ ! -f "$COMPILE_DB" ]; then
  echo "compile_commands.json not found" >&2
  exit 1
fi

# 2. .c 파일 리스트 뽑아서 bc 생성
mkdir -p bc

jq -r '.[] | select(.file | endswith(".c")) | .file' "$COMPILE_DB" \
  | sort -u > c_files.txt

while read -r src; do
  out="bc/$(echo "$src" | sed 's#/#_#g' | sed 's#\.c$#.bc#')"
  clang -O0 -g -emit-llvm -c "$src" -o "$out"
done < c_files.txt

# 3. all.bc 링크 후 call graph 추출
llvm-link bc/*.bc -o all.bc
opt -passes=print-callgraph -disable-output all.bc 2> cg.txt
