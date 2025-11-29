# core/tasks.py (보완된 버전)

from celery import shared_task
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import AnalysisTask
import subprocess
import shutil
import json
import csv
from pathlib import Path
import os # 파일 경로 조작을 위해 추가

CLANG_CG_SCRIPT = os.path.join(
    settings.BASE_DIR,
    'scripts',
    'clang_cg.sh',
)

def get_repo_path(task_id):
    return Path(f'/tmp/analysis_{task_id}')

# 모든 분석 작업을 처리하는 공통 헬퍼 함수
def _execute_analysis(task_id, step_name, command_list, output_filename, path_field, preprocessing=None):
    task = get_object_or_404(AnalysisTask, pk=task_id)
    repo_dir = get_repo_path(task_id)
    output_filepath = repo_dir / output_filename # 결과 파일 경로
    
    # 상태 업데이트: RUNNING으로 설정하고 현재 단계 지정
    task.status = 'RUNNING'
    task.current_step = step_name.upper()
    task.save(update_fields=['status', 'current_step'])
    
    try:
        # if not repo_dir.exists():
        #      raise FileNotFoundError(f"Repository not found. Run CLONING first.")

        # is_othertool = step_name.upper() == 'CPPLINT' or step_name.upper() == 'LIZARD'

        # if is_othertool:
        #     v_check = False
        #     v_stderr = subprocess.STDOUT
        # else:
        #     v_check = True
        #     v_stderr = subprocess.PIPE

        # # -- 실제 분석 명령어 실행 --
        # # stdout을 파일로 리다이렉션하여 원시 데이터 저장
        # with open(output_filepath, 'w') as f:
        #      subprocess.run(
        #         command_list, 
        #         cwd=str(repo_dir),
        #         check=v_check, 
        #         stdout=f, # 결과를 파일로 출력
        #         stderr=v_stderr, # 에러는 파이프로 받음
        #         text=True
        #      )
        
        # # 파일 경로 저장 및 상태 업데이트
        # setattr(task, path_field, output_filename)

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

        task.status = 'RUNNING'
        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        task.status = 'FAILED'
        task.error_message = f"{step_name} Failed: {str(e)}"
        task.save()
        return 'FAILED'
        
    task.save()
    return 'SUCCESS'

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
    # Infer 결과를 'infer_result.txt' 파일로 저장
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
    # Cpplint 결과를 'cpplint_result.txt' 파일로 저장
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