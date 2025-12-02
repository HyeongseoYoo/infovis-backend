# core/views.py
from rest_framework import views, status, generics
from rest_framework.response import Response
from rest_framework import serializers
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
import json

from .models import AnalysisTask
from .tasks import (
    start_cloning_task, run_infer_task, run_cpplint_task, 
    run_lizard_task, run_clang_build_task, run_preprocessing_task,
    load_task_json, build_task_zip, run_cleanup_task
)

# --- 1. Serializers ---

class TaskStatusSerializer(serializers.ModelSerializer):
    """
    작업의 현재 상태 및 진행 단계를 표시하기 위한 Serializer.
    """
    class Meta:
        model = AnalysisTask
        fields = ('id', 'github_url', 'status', 'current_step', 'created_at', 'error_message')

class TaskResultSerializer(serializers.ModelSerializer):
    """
    최종 분석 결과 (result_data)를 반환하기 위한 Serializer.
    """
    class Meta:
        model = AnalysisTask
        fields = ('id', 'result_data', 'status')


# --- 2. API Views ---

# 1. 분석 시작 (Clone)
class StartAnalysisView(views.APIView):
    """
    GitHub URL을 받아 AnalysisTask를 생성하고 CLONING Celery Task를 시작합니다.
    """
    def post(self, request):
        github_url = request.data.get('github_url')
        if not github_url:
            return Response({"error": "GitHub URL is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Task 생성 및 상태 초기화 (PENDING, NONE)
        task = AnalysisTask.objects.create(github_url=github_url, status='PENDING', current_step='NONE')
        
        # Celery Task 시작
        start_cloning_task.delay(task.id, github_url)
        
        return Response({
            "task_id": task.id, 
            "status": "RUNNING", # Celery 등록 후 RUNNING 상태로 가정
            "current_step": "CLONING",
            "message": "Cloning task initiated. Check status API for updates."
        }, status=status.HTTP_202_ACCEPTED)

# 2. 단계별 분석 실행
class RunAnalysisStepView(views.APIView):
    """
    Task ID와 단계 이름(infer, cpplint 등)을 받아 해당 Celery Task를 시작합니다.
    """
    def post(self, request, task_id, step_name):
        try:
            task = AnalysisTask.objects.get(pk=task_id)
        except AnalysisTask.DoesNotExist:
            return Response({"error": "Task not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # 단계별 Celery Task 매핑
        task_map = {
            'clang': run_clang_build_task,
            'infer': run_infer_task,
            'cpplint': run_cpplint_task,
            'lizard': run_lizard_task,
            'preprocess': run_preprocessing_task,
            'cleanup': run_cleanup_task,
        }

        if step_name not in task_map:
            return Response({"error": "Invalid analysis step."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Celery Task 등록
        task_map[step_name].delay(task_id)
        
        return Response({
            "task_id": task_id, 
            "status": "RUNNING",
            "current_step": step_name.upper(), # 다음 단계로 업데이트될 예정
            "message": f"Step '{step_name}' task initiated."
        }, status=status.HTTP_202_ACCEPTED)

# 3. 상태 조회
class TaskStatusView(generics.RetrieveAPIView):
    """
    Task ID로 현재 상태 (status, current_step)를 조회합니다.
    """
    queryset = AnalysisTask.objects.all()
    serializer_class = TaskStatusSerializer

# 4. 결과 조회
class TaskResultView(generics.RetrieveAPIView):
    """
    Task ID로 최종 분석 결과 (result_data)를 조회합니다.
    COMPLETED 상태인 Task만 반환합니다.
    """
    queryset = AnalysisTask.objects.all()
    serializer_class = TaskResultSerializer
    
    def get_object(self):
        # URL의 pk(task_id)를 사용하여 쿼리셋에서 객체를 찾습니다.
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs['pk'])
        return obj
    
# 4-1. 결과 json 각각 전달
class TaskFileJSONView(views.APIView):
    """
    /tmp/analysis_<task_id>/<filename> 을 읽어 JSON으로 반환하는 공통 View.
    자식 클래스에서 filename만 override.
    """
    filename: str | None = None

    def get(self, request, pk, *args, **kwargs):
        if self.filename is None:
            return Response(
                {"detail": "filename is not configured."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            data = load_task_json(pk, self.filename)
        except FileNotFoundError as e:
            # Task 없거나, 파일 없을 때 둘 다 여기서 처리 가능
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )
        except json.JSONDecodeError:
            return Response(
                {"detail": f"{self.filename} is not a valid JSON file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(data, status=status.HTTP_200_OK)


class TaskCGView(TaskFileJSONView):
    filename = "cg_filtered.json"

class TaskWarningsView(TaskFileJSONView):
    filename = "warnings.json"

class TaskFunctionsView(TaskFileJSONView):
    filename = "functions.json"

# 4-2. 결과 json zip file download
class TaskZipDownloadView(views.APIView):
    """
    /tmp/analysis_<task_id> 내의
      - cg_filtered.json
      - warnings.json
      - functions.json
    세 파일 중, 존재하는 것만 ZIP으로 묶어 내려줌.
    세 개 모두 없으면 404.
    """

    filenames = ["cg_filtered.json", "warnings.json", "functions.json"]

    def get(self, request, pk, *args, **kwargs):
        try:
            zip_bytes = build_task_zip(pk, self.filenames)
        except FileNotFoundError as e:
            # Task가 없거나, 결과 파일이 아예 없는 경우
            return Response(
                {"detail": str(e)},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = HttpResponse(zip_bytes, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="analysis_{pk}.zip"'
        return response