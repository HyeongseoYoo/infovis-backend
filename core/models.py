from django.db import models

class AnalysisTask(models.Model):
    # 1. 상태 필드 (결과 상태만 명확히 표시)
    STATUS_CHOICES = [
        ('PENDING', '대기 중'),
        ('RUNNING', '실행 중'),
        ('COMPLETED', '완료'),
        ('FAILED', '실패'),
    ]
    
    # 2. 진행 단계 필드 (현재 어떤 단계에 있는지 표시)
    STEP_CHOICES = [
        ('NONE', '시작 전'),
        ('CLONING', 'GIT Clone'),
        ('CLANG', 'Clang Build'),
        ('INFER', 'Infer 분석'),
        ('CPPLINT', 'Cpplint 분석'),
        ('LIZARD', 'Lizard 분석'),
        ('PREPROCESSING', '전처리'),
        ('CLEANUP', 'Repo 삭제')
    ]
    
    github_url = models.URLField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default='NONE')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # raw 데이터 저장
    infer_path = models.CharField(max_length=255, null=True, blank=True)
    cpplint_path = models.CharField(max_length=255, null=True, blank=True)
    lizard_path = models.CharField(max_length=255, null=True, blank=True)
    clang_path = models.CharField(max_length=255, null=True, blank=True)

    # 최종 시각화 데이터 저장 (PostgreSQL의 JSONField 사용)
    result_data = models.JSONField(null=True, blank=True) 
    error_message = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Task {self.id} - {self.status}"
