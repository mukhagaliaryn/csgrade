from django.urls import path
from .views import exam, auth, account, attempt

app_name = "customer"

urlpatterns = [
    # auth urls...
    path("auth/login/", auth.login_view, name="login"),
    path("auth/register/", auth.register_view, name="register"),
    path("auth/logout/", auth.logout_view, name="logout"),

    # account urls...
    path('account/me/', account.account_view, name="account"),
    path('account/settings/', account.settings_view, name="settings"),

    # customer urls...
    path("", exam.customer_dashboard_view, name="dashboard"),
    path("exams/", exam.customer_exams_view, name="exams"),
    path("exams/<int:exam_id>/", exam.customer_exam_detail_view, name="exam_detail"),
    path("exams/<int:exam_id>/start/", exam.customer_exam_start_view, name="exam_start"),

    # attempt urls...
    path("attempts/<int:attempt_id>/", attempt.attempt_detail_view, name="attempt_detail"),
    path("attempts/<int:attempt_id>/question/", attempt.attempt_question_view, name="attempt_question"),

    # HTMX save (question_id URL-да!)
    path("attempts/<int:attempt_id>/q/<int:question_id>/answer/", attempt.attempt_answer_view, name="attempt_answer"),

    path("attempts/<int:attempt_id>/q/<int:question_id>/speaking/", attempt.attempt_speaking_upload_view,
         name="attempt_speaking_upload"),
    path("attempts/<int:attempt_id>/q/<int:question_id>/writing/", attempt.attempt_writing_submit_view,
         name="attempt_writing_submit"),
    path("attempts/<int:attempt_id>/submit/", attempt.attempt_submit_view, name="attempt_submit"),
    path("attempts/<int:attempt_id>/review/", attempt.attempt_review_view, name="attempt_review"),
]
