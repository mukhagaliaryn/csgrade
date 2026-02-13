from django.urls import path
from . import views

app_name = "manager"

urlpatterns = [
    path("", views.manager_dashboard_view, name="dashboard"),
    path("attempts/<int:attempt_id>/review/", views.manager_attempt_review_view, name="attempt_review"),
]