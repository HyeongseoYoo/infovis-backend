#!/bin/bash
# run_cg.sh: CMake 기반으로 Clang Build 및 Call Graph 추출을 수행하는 스크립트
# 이 스크립트는 Celery Task에 의해 클론된 리포지토리의 루트 디렉토리에서 실행됩니다.

# 에러 발생 시 즉시 종료하고, 파이프라인의 오류도 즉시 종료하도록 설정
set -euo pipefail

REPO_DIR=$(pwd)
NPROCS=$(nproc)
COMPILE_DB="build/compile_commands.json"
ALL_BC_FILENAME="all.bc"

echo "======================================================"
echo "Starting Clang Build and Call Graph Extraction (PID: $$)"
echo "Repo Root: $REPO_DIR"
echo "Cores: $NPROCS"
echo "======================================================"

# 1. Clang Build 환경 설정 및 compile_commands.json 생성
echo "1. Configuring CMake Build..."
mkdir -p build
cd build

# CMAKE_EXPORT_COMPILE_COMMANDS=ON을 통해 compile_commands.json 생성
cmake -DCMAKE_C_COMPILER=clang -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ..

echo "2. Running CMake Build..."
# Build 실행 (cmake 빌드는 CMAKE_EXPORT_COMPILE_COMMANDS가 설정되어 있으면 
# 실제로 빌드가 완료되지 않아도 compile_commands.json을 생성할 수 있습니다.
# 하지만 Bitcode 생성에 필요한 모든 파일이 준비되도록 전체 빌드를 시도합니다.)
cmake --build . -j"$NPROCS"

if [ ! -f "compile_commands.json" ]; then
    echo "에러: compile_commands.json이 'build/' 폴더에 생성되지 않았습니다. Clang 빌드 실패." >&2
    exit 1
fi

# 2. Bitcode 생성
cd "$REPO_DIR" # 리포지토리 루트로 돌아오기
mkdir -p bc
C_FILES_LIST="c_files.txt"

# jq를 사용하여 빌드할 .c 파일 목록 추출 및 정리
echo "3. Extracting list of .c files from compile_commands.json..."
jq -r '.[] | select(.file | endswith(".c")) | .file' "$COMPILE_DB" \
  | sort -u > "$C_FILES_LIST"

if [ ! -s "$C_FILES_LIST" ]; then
    echo "경고: 분석할 .c 파일을 찾지 못했습니다. Bitcode 생성 단계를 건너뜁니다." >&2
    exit 1
fi

echo "4. Generating Bitcode (.bc) files..."
while IFS= read -r src; do
  # 출력 경로 설정 (경로 충돌 방지 위해 원본 경로를 기반으로 파일명 생성)
  # 예: src/main.c -> src_main.bc
  out_filename=$(echo "$src" | sed 's#/#_#g' | sed 's#\.c$#.bc#')
  out_path="bc/$out_filename"
  
  # clang 컴파일: -O0 -g -emit-llvm -c 옵션을 사용하여 Bitcode 생성
  # $src 경로가 compile_commands.json에 있는 상대 경로와 일치해야 합니다.
  clang -O0 -g -emit-llvm -c "$src" -o "$out_path"
done < "$C_FILES_LIST"

# 3. 모든 Bitcode 파일 링크
echo "5. Linking all Bitcode files into $ALL_BC_FILENAME..."
BC_FILES=$(find bc/ -name "*.bc")

if [ -z "$BC_FILES" ]; then
    echo "에러: Bitcode 파일이 생성되지 않았습니다. Call Graph 추출 실패." >&2
    exit 1
fi

echo "6. Extracting Call Graph per module (to STDOUT)..." >&2
for bc in $BC_FILES; do
  echo ";; ===== Callgraph for module: $bc =====" >&2
  # opt는 stderr로 call graph를 쓰니까, 2>&1 해서 stdout으로 보냄
  opt -passes=print-callgraph -disable-output "$bc" 2>&1
done

echo "======================================================"
echo "Call Graph extraction completed successfully."
echo "======================================================"