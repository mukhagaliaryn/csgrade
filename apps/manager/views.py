import csv

from django.core.paginator import Paginator
from django.db.models import FloatField, Value, ExpressionWrapper, F, Avg, Q
from django.db.models.functions import Cast, NullIf
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET
from openpyxl import Workbook

from apps.main.services.review import _build_review_response
from core.models import Exam, SectionAttempt, ExamAttempt
from core.utils.decorators import role_required


# manager_dashboard page
# ======================================================================================================================
@role_required('manager')
def manager_dashboard_view(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    exam_id = request.GET.get("exam", "").strip()
    export = request.GET.get("export", "").strip()

    base_attempts = ExamAttempt.objects.select_related("user", "exam")
    if status:
        base_attempts = base_attempts.filter(status=status)

    if exam_id:
        base_attempts = base_attempts.filter(exam_id=exam_id)

    if q:
        base_attempts = base_attempts.filter(
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(exam__title__icontains=q) |
            Q(id__icontains=q)
        )

    finished_attempts = base_attempts.filter(status="finished")
    total_attempts = finished_attempts.count()

    overall_avg = (
        finished_attempts
        .exclude(total_score__isnull=True)
        .annotate(
            percent=ExpressionWrapper(
                Cast(F("total_score"), FloatField()) * Value(100.0) /
                NullIf(Cast(F("max_total_score"), FloatField()), 0.0),
                output_field=FloatField(),
            )
        )
        .aggregate(avg=Avg("percent"))
        .get("avg")
    )

    section_avg_qs = (
        SectionAttempt.objects
        .filter(attempt__status="finished")
        .annotate(
            percent=ExpressionWrapper(
                Cast(F("score"), FloatField()) * Value(100.0) /
                NullIf(Cast(F("max_score"), FloatField()), 0.0),
                output_field=FloatField(),
            )
        )
        .values("section__section_type")
        .annotate(avg=Avg("percent"))
    )
    section_avg_map = {
        row["section__section_type"]: row["avg"]
        for row in section_avg_qs
    }

    SECTION_KEYS = [
        ("listening", "Тыңдалым (Listening)"),
        ("reading", "Оқылым (Reading)"),
        ("speaking", "Айтылым (Speaking)"),
        ("writing", "Жазылым (Writing)"),
    ]
    section_progress = [
        {
            "key": key,
            "label": label,
            "avg": section_avg_map.get(key),
        }
        for key, label in SECTION_KEYS
    ]

    # 🔹 Excel export
    if export == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Емтихан нәтижелері"

        ws.append([
            "ID",
            "Студент",
            "Емтихан",
            "Статус",
            "Жалпы балл",
            "Макс. балл",
            "Пайыздық көрсеткіші",
            "Басталған уақыты",
            "Аяқталған уақыты",
        ])

        for a in finished_attempts:
            percent = 0
            if a.max_total_score:
                percent = round((a.total_score / a.max_total_score) * 100, 2)

            ws.append([
                a.id,
                a.user.username,
                a.exam.title,
                a.get_status_display(),
                a.total_score,
                a.max_total_score,
                percent,
                str(a.started_at),
                str(a.finished_at),
            ])

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="exam_attempts.xlsx"'
        wb.save(response)
        return response

    # 🔹 Pagination
    attempts = base_attempts.order_by("-finished_at", "-id")
    paginator = Paginator(attempts, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "total_attempts": total_attempts,
        "overall_avg": overall_avg,
        "section_progress": section_progress,
        "attempts": attempts,
        "exam_options": Exam.objects.all(),
        "page_obj": page_obj,
    }
    return render(request, "app/manager/page.html", context)



@require_GET
@role_required("manager")
def manager_attempt_review_view(request, attempt_id: int):
    attempt = get_object_or_404(
        ExamAttempt.objects.select_related("user", "exam"),
        pk=attempt_id
    )
    return _build_review_response(request, attempt, review_url_name="manager:attempt_review")
