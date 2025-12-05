#!/bin/bash
# run_cg.sh: CMake 기반으로 Clang Build 및 Call Graph 추출을 수행하는 스크립트
# 이 스크립트는 Celery Task에 의해 클론된 리포지토리의 루트 디렉토리에서 실행됩니다.

set -euo pipefail
set -x

REPO_DIR="$(pwd)"
BUILD_DIR="$REPO_DIR/build"
NPROCS="$(nproc)"
COMPILE_DB="$BUILD_DIR/compile_commands.json"
BC_DIR="$REPO_DIR/bc"
ALL_BC_FILENAME="all.bc"

echo "======================================================"
echo "Starting Clang Build and Call Graph Extraction (PID: $$)"
echo "Repo Root: $REPO_DIR"
echo "Cores: $NPROCS"
echo "======================================================"

echo "1. Configuring CMake Build..."
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# compile_commands.json 생성
cmake -DCMAKE_C_COMPILER=clang -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ..

if [ ! -f "$COMPILE_DB" ]; then
    echo "에러: compile_commands.json이 'build/' 폴더에 생성되지 않았습니다. CMake 설정 실패." >&2
    exit 1
fi

echo "2. Running CMake Build (optional)..."
# 빌드 실패해도 경고만 찍고 계속 진행 (링크 실패 등)
if ! cmake --build . -j"$NPROCS"; then
    echo "[WARN] CMake build failed (아마 링크 단계에서 실패했을 수 있음)." >&2
    echo "[WARN] call graph 추출에는 compile_commands.json만 필요하므로 계속 진행합니다." >&2
fi

cd "$REPO_DIR"
mkdir -p "$BC_DIR"
C_FILES_LIST="$REPO_DIR/c_files.txt"

echo "3. Extracting list of .c files from compile_commands.json..."
# 각 엔트리를 base64로 인코딩해서 안전하게 루프 처리
jq -r '.[] | select(.file | endswith(".c")) | @base64' "$COMPILE_DB" > "$C_FILES_LIST"

if [ ! -s "$C_FILES_LIST" ]; then
    echo "경고: 분석할 .c 파일을 찾지 못했습니다. Bitcode 생성 실패." >&2
    exit 1
fi

echo "4. Generating Bitcode (.bc) files using compile_commands.json..."
while IFS= read -r entry_b64; do
  # base64 → JSON
  entry_json="$(echo "$entry_b64" | base64 --decode)"

  # file / directory / command 추출
  src_file="$(echo "$entry_json" | jq -r '.file')"
  src_dir="$(echo "$entry_json" | jq -r '.directory')"
  orig_cmd="$(echo "$entry_json" | jq -r '.command')"

  # 출력 파일 이름 결정 (경로 → 언더스코어)
  out_filename="$(echo "$src_file" | sed 's#/#_#g' | sed 's#\.c$#.bc#')"
  out_path="$BC_DIR/$out_filename"

  echo "  - compiling to bitcode: $src_file -> $out_path"

  # 원래 컴파일러 이름(gcc/cc/clang 등)을 떼고 나머지 인자만 사용
  mapfile -t args < <(echo "$entry_json" | jq -r '.arguments[]')

  # 첫 번째 요소(컴파일러) 제거
  unset 'args[0]'

  (
    cd "$src_dir"
    echo "  - Executing: clang ${args[*]} -O0 -g -emit-llvm -c -o \"$out_path\""
    clang "${args[@]}" -O0 -g -emit-llvm -c -o "$out_path"
  )

done < "$C_FILES_LIST"

echo "5. Collecting Bitcode files..."
BC_FILES=$(find "$BC_DIR" -name "*.bc")

if [ -z "$BC_FILES" ]; then
    echo "에러: Bitcode 파일이 생성되지 않았습니다. Call Graph 추출 실패." >&2
    exit 1
fi

echo "6. Extracting Call Graph per module (to STDOUT)..." >&2
for bc in $BC_FILES; do
  echo ";; ===== Callgraph for module: $bc =====" >&2
  opt -passes=print-callgraph -disable-output "$bc" 2>&1
done

echo "======================================================"
echo "Call Graph extraction completed successfully."
echo "======================================================"
