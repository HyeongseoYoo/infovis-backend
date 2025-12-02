# core/tasks.py (보완된 버전)

from celery import shared_task
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import AnalysisTask
import subprocess
import shutil
import json
from pathlib import Path
import os
import io
import zipfile

CLANG_CG_SCRIPT = os.path.join(
    settings.BASE_DIR,
    'scripts',
    'clang_cg.sh',
)

def get_repo_path(task_id):
    base_dir = Path("/data")
    base_dir.mkdir(parents=True, exist_ok=True)
    task_dir = base_dir / f"analysis_{task_id}"
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir

def ensure_empty_json(repo_dir: Path, filename: str):
    repo_dir.mkdir(parents=True, exist_ok=True)
    json_path = repo_dir / filename
    
    if not json_path.exists():
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([], f)

# 모든 분석 작업을 처리하는 공통 헬퍼 함수
def _execute_analysis(task_id, step_name, command_list, output_filename, path_field, preprocessing=None):
    task = get_object_or_404(AnalysisTask, pk=task_id)
    repo_dir = get_repo_path(task_id)
    output_filepath = repo_dir / output_filename # 결과 파일 경로
    
    # 상태 업데이트: RUNNING으로 설정하고 현재 단계 지정
    task.status = 'RUNNING'
    task.current_step = step_name.upper()
    task.save(update_fields=['status', 'current_step'])
    
    is_othertool = step_name.upper() == 'CPPLINT' or step_name.upper() == 'LIZARD'

    try:
        if not repo_dir.exists():
             raise FileNotFoundError(f"Repository not found. Run CLONING first.") 

        if is_othertool:
            v_check = False
            v_stderr = subprocess.STDOUT
        else:
            v_check = True
            v_stderr = subprocess.PIPE

        # -- 실제 분석 명령어 실행 --
        # stdout을 파일로 리다이렉션하여 원시 데이터 저장
        with open(output_filepath, 'w') as f:
             subprocess.run(
                command_list, 
                cwd=str(repo_dir),
                check=v_check, 
                stdout=f, # 결과를 파일로 출력
                stderr=v_stderr, # 에러는 파이프로 받음
                text=True
             )
        
        # 파일 경로 저장 및 상태 업데이트
        setattr(task, path_field, output_filename)

        if preprocessing is not None:
            script_path = Path(settings.BASE_DIR) / "core" / "script" / preprocessing
            preprocess_cmd = [
                'python3',
                str(script_path),
            ]
            subprocess.run(
                preprocess_cmd,
                cwd=str(repo_dir),
                check=True,
                text=True
            )

        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        task.status = 'FAILED'
        if isinstance(e, subprocess.CalledProcessError):
            err_detail = e.stderr or ''
            task.error_message = f"{step_name} Failed: {str(e)}\n{err_detail}"
        else:
            task.error_message = f"{step_name} Failed: {str(e)}"
        task.save()
        return 'FAILED'
    
    task.status = 'COMPLETED'
    task.save()
    return 'SUCCESS'

# 결과 json 파일 1개 읽는 헬퍼 함수
def load_task_json(task_id: int, filename: str):
    """
    COMPLETED 상태의 Task에 대해 /tmp/analysis_<task_id>/<filename> 을 읽어
    파싱된 JSON 객체를 반환합니다.
    """
    # Task 존재 여부만 확인 (status 필터 X)
    get_object_or_404(AnalysisTask, pk=task_id)

    repo_dir = get_repo_path(task_id)
    file_path = repo_dir / filename

    if not file_path.is_file():
        raise FileNotFoundError(f"{filename} not found for task {task_id}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data

# 결과 josn 파일을 zip 하는 헬퍼 함수
def build_task_zip(task_id: int, filenames=None) -> bytes:
    """
    COMPLETED 상태의 Task에 대해 /tmp/analysis_<task_id> 안의
    주어진 filenames들을 하나의 ZIP 바이트로 만들어 반환합니다.
    """
    # Task 존재 여부만 확인
    get_object_or_404(AnalysisTask, pk=task_id)

    repo_dir = get_repo_path(task_id)

    if filenames is None:
        filenames = ["cg_filtered.json", "warnings.json", "functions.json"]

    memory_file = io.BytesIO()
    added_any = False

    with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            file_path = repo_dir / filename
            if file_path.is_file():
                zf.write(file_path, arcname=filename)
                added_any = True

    if not added_any:
        raise FileNotFoundError(f"No result files found for task {task_id}")
    
    memory_file.seek(0)
    return memory_file.getvalue()


# --- Step 0: Git Clone Task ---
@shared_task
def start_cloning_task(task_id, github_url):
    task = get_object_or_404(AnalysisTask, pk=task_id)
    repo_dir = get_repo_path(task_id)
    task.status = 'RUNNING'
    task.current_step = 'CLONING'
    task.save(update_fields=['status', 'current_step'])

    success = False
    try:
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        subprocess.run(
            ['git', 'clone', '--depth', '1', github_url, str(repo_dir)], 
            check=True, 
            capture_output=True, 
            text=True
        )
        success = True
        task.status = 'COMPLETED'

    except subprocess.CalledProcessError as e:
        task.status = 'FAILED'
        task.error_message = f"Git Clone Failed: {e.stderr}"
    
    if not success:
        task.status = 'FAILED'
    
    task.save()
    return task.status

# --- Step 1: Clang Build/Call Graph Task ---
@shared_task
def run_clang_build_task(task_id):
    # Clang/CG 결과를 'cg.json.txt' 파일로 저장 (JSON 형태의 TXT)
    return _execute_analysis(
        task_id, 
        'CLANG', 
        [CLANG_CG_SCRIPT],
        'cg.txt', 
        'clang_path',
        'cg_preprocessing.py'
    )
    
# --- Step 2: Infer Task ---
@shared_task
def run_infer_task(task_id):
    repo_dir = get_repo_path(task_id)
    ensure_empty_json(repo_dir, 'infer_result.json')

    return _execute_analysis(
        task_id, 
        'INFER', 
        ['infer', 'run', '--', 'make'], # make 실행은 repo_dir 내부에서 
        'infer_result.txt', 
        'infer_path',
        'infer_preprocessing.py'
    )

# --- Step 3: Cpplint Task ---
@shared_task
def run_cpplint_task(task_id):
    repo_dir = get_repo_path(task_id)
    ensure_empty_json(repo_dir, 'cpplint_result.json')

    return _execute_analysis(
        task_id, 
        'CPPLINT', 
        ['cpplint', '--recursive', str(repo_dir)], 
        'cpplint_result.txt', 
        'cpplint_path',
        'cpplint_preprocessing.py'
    )

# --- Step 4: Lizard Task ---
@shared_task
def run_lizard_task(task_id):
    repo_dir = get_repo_path(task_id)
    # Lizard 결과를 'lizard_result.csv' 파일로 저장
    return _execute_analysis(
        task_id, 
        'LIZARD', 
        ['lizard', '-o', 'lizard_result.csv'],
        'lizard_result.txt', 
        'lizard_path',
        'lizard_preprocessing.py'
    )


# --- Step 5: Preprocessing Task ---
def run_script(script_name, repo_dir):
    base_dir = Path(settings.BASE_DIR)

    script_path = base_dir / "core" / "script" / script_name
    if not script_path.is_file():
        raise FileNotFoundError(f"Preprocessing script not found: {script_path}")

    subprocess.run(
        ["python3", str(script_path)],
        cwd=str(repo_dir),
        check=True,
        text=True,
    )


@shared_task
def run_preprocessing_task(task_id):
    task = get_object_or_404(AnalysisTask, pk=task_id)
    repo_dir = get_repo_path(task_id)

    task.status = 'RUNNING'
    task.current_step = 'PREPROCESSING'
    task.save(update_fields=['status', 'current_step'])
    
    try:

        # Filtering Function
        run_script("cg_filter.py", repo_dir)

        # Add Function Data and Merging Warnings
        run_script("cpplint_add_function.py", repo_dir)
        run_script("merge_warnings.py", repo_dir)
        
        # Add Warning Data and Filtering
        run_script("lizard_filter.py", repo_dir)

        # 최종 상태 저장 및 정리
        final_json_data = {}
        task.result_data = final_json_data
        task.status = 'COMPLETED'
        
    except Exception as e:
        task.status = 'FAILED'
        task.error_message = f"Preprocessing Failed: {str(e)}"

    finally:
        # 작업 완료 후 디렉토리 정리 !!! 살려야됨!!
        # if repo_dir.exists():
        #     shutil.rmtree(repo_dir)
        
        task.save()
