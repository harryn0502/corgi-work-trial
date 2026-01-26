from django.urls import path
from api.views import health_check, BatchAnalyzeView

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("batch-analyze/", BatchAnalyzeView.as_view(), name="batch-analyze"),
]
