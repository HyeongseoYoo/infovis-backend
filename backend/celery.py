# analysis_backend/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# Django settings에서 Celery 관련 설정 읽기
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django 앱의 tasks.py 파일을 자동으로 찾음
app.autodiscover_tasks()

# Celery가 작업 디렉토리를 정리할 수 있도록 설정
# Task 완료 후 로그 확인에 유용할 수 있습니다.
# @app.task(bind=True)
# def debug_task(self):
#     print(f'Request: {self.request!r}')