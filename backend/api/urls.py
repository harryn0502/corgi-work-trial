from django.urls import path
from api.views import HealthView, AnalyzeView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("analyze/", AnalyzeView.as_view(), name="analyze"),
]
