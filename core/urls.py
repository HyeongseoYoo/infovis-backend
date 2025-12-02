from django.urls import path
from .views import StartAnalysisView, RunAnalysisStepView, TaskStatusView, TaskResultView, TaskCGView, TaskWarningsView, TaskFunctionsView, TaskZipDownloadView

urlpatterns = [
    # POST 요청: 분석 Task 시작 (StartAnalysisView가 처리)
    path('tasks/start/', StartAnalysisView.as_view(), name='start_analysis'),
    
    # POST 요청: 특정 Task의 다음 분석 단계 실행
    path('tasks/<int:task_id>/run/<str:step_name>/', RunAnalysisStepView.as_view(), name='run_analysis_step'),
    
    # GET 요청: Task 상태 조회
    path('tasks/<int:pk>/status/', TaskStatusView.as_view(), name='task_status'),
    
    # GET 요청: Task 최종 결과 조회
    path('tasks/<int:pk>/result/', TaskResultView.as_view(), name='task_result'),

    # 개별 JSON 전달
    path('tasks/<int:pk>/cg/', TaskCGView.as_view(), name='task_cg'),
    path('tasks/<int:pk>/warnings/', TaskWarningsView.as_view(), name='task_warnings'),
    path('tasks/<int:pk>/functions/', TaskFunctionsView.as_view(), name='task_functions'),

    # ZIP 다운로드
    path('tasks/<int:pk>/download/', TaskZipDownloadView.as_view(), name='task_download'),
]