from django.contrib import messages
from django.db.models import OuterRef, Exists, Prefetch, Subquery, IntegerField, Value, F, ExpressionWrapper, FloatField
from django.db.models.aggregates import Avg, Count, Sum
from django.db.models.functions import Coalesce, Cast, NullIf
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from core.utils.decorators import role_required
from core.models import ExamAttempt, SectionAttempt, Exam, Section, Question, AttemptStatus


# customer dashboard page
# ======================================================================================================================
@role_required("customer")
def customer_dashboard_view(request):
    user = request.user
    recent_attempts = (
        ExamAttempt.objects
        .filter(user=user)
        .order_by("-finished_at", "-id")[:10]
    )
    overall_avg = (
        ExamAttempt.objects
        .filter(user=user)
        .exclude(total_score__isnull=True)
        .exclude(max_total_score__isnull=True)
        .annotate(
            percent=ExpressionWrapper(
                Cast(F("total_score"), FloatField()) * Value(100.0) / NullIf(Cast(F("max_total_score"), FloatField()), 0.0),
                output_field=FloatField(),
            )
        )
        .aggregate(avg=Avg("percent"))
        .get("avg")
    )
    section_avg_qs = (
        SectionAttempt.objects
        .filter(attempt__user=user)
        .exclude(score__isnull=True)
        .exclude(max_score__isnull=True)
        .annotate(
            percent=ExpressionWrapper(
                Cast(F("score"), FloatField()) * Value(100.0) / NullIf(Cast(F("max_score"), FloatField()), 0.0),
                output_field=FloatField(),
            )
        )
        .values("section__section_type")
        .annotate(avg=Avg("percent"))
    )
    section_avg_s = {row["section__section_type"]: row["avg"] for row in section_avg_qs}

    SECTION_KEYS = [
        ("listening", "Тыңдалым (Listening)"),
        ("reading", "Оқылым (Reading)"),
        ("speaking", "Айтылым (Speaking)"),
        ("writing", "Жазылым (Writing)"),
    ]
    section_progress = []
    for key, label in SECTION_KEYS:
        section_progress.append({
            "key": key,
            "label": label,
            "avg": section_avg_s.get(key),
        })

    context = {
        "profile_user": user,
        "overall_avg": overall_avg,
        "section_progress": section_progress,
        "recent_attempts": recent_attempts,
    }
    return render(request, "app/main/page.html", context)


# customer exams page
# ======================================================================================================================
@role_required("customer")
def customer_exams_view(request):
    user = request.user
    user_has_attempt = ExamAttempt.objects.filter(
        user=user,
        exam_id=OuterRef("pk"),
    )
    exams = (
        Exam.objects
        .filter(is_published=True)
        .order_by("-id")
        .annotate(
            is_registered=Exists(user_has_attempt),
            section_count=Count("sections", distinct=True),
            question_count=Count("sections__questions", distinct=True),
        )
    )
    return render(request, "app/main/exams/page.html", {"exams": exams})


# customer exam detail page
# ======================================================================================================================
@role_required("customer")
def customer_exam_detail_view(request, exam_id: int):
    user = request.user
    section_sum_time_sq = (
        Section.objects
        .filter(exam_id=OuterRef("pk"))
        .values("exam_id")
        .annotate(total=Sum("time_limit"))
        .values("total")[:1]
    )
    section_sum_score_sq = (
        Section.objects
        .filter(exam_id=OuterRef("pk"))
        .values("exam_id")
        .annotate(total=Sum("max_score"))
        .values("total")[:1]
    )
    question_count_sq = (
        Question.objects
        .filter(section__exam_id=OuterRef("pk"))
        .values("section__exam_id")
        .annotate(total=Count("id"))
        .values("total")[:1]
    )
    exam_qs = (
        Exam.objects
        .annotate(
            is_registered=Exists(
                ExamAttempt.objects.filter(user=user, exam_id=OuterRef("pk"))
            ),
            section_count=Count("sections", distinct=True),
            question_count=Coalesce(Subquery(question_count_sq, output_field=IntegerField()), Value(0)),
            time_limit=Coalesce(Subquery(section_sum_time_sq, output_field=IntegerField()), Value(0)),
            max_total_score=Coalesce(Subquery(section_sum_score_sq, output_field=IntegerField()), Value(0)),
        )
        .prefetch_related(
            Prefetch(
                "sections",
                queryset=Section.objects.order_by("order").prefetch_related(
                    Prefetch("questions", queryset=Question.objects.order_by("order"))
                ),
            )
        )
    )
    exam = get_object_or_404(exam_qs, pk=exam_id)
    attempt = (
        ExamAttempt.objects
        .filter(user=user, exam=exam)
        .order_by("-id")
        .first()
    )
    context = {
        "exam": exam,
        "attempt": attempt,
    }
    return render(request, "app/main/exams/detail/page.html", context)


# customer exam start action
# ======================================================================================================================
@role_required("customer")
def customer_exam_start_view(request, exam_id: int):
    user = request.user
    exam = get_object_or_404(Exam, pk=exam_id)

    has_questions = Question.objects.filter(section__exam=exam).exists()
    if not has_questions:
        messages.warning(
            request,
            "Бұл тестте әлі сұрақтар жоқ. Кейінірек қайта тексеріңіз."
        )
        return redirect("customer:exam_detail", exam.pk)

    locked_attempt = (
        ExamAttempt.objects
        .select_related("exam")
        .filter(user=user, status=AttemptStatus.IN_PROGRESS)
        .exclude(exam=exam)
        .first()
    )
    if locked_attempt:
        messages.warning(
            request,
            f"Сізде аяқталмаған тест бар: «{locked_attempt.exam.title}». "
            "Алдымен соны аяқтаңыз."
        )
        return redirect("customer:attempt_detail", locked_attempt.pk)

    attempt = ExamAttempt.objects.filter(user=user, exam=exam).first()
    if attempt:
        return redirect("customer:attempt_detail", attempt.pk)

    attempt = ExamAttempt.objects.create(
        user=user,
        exam=exam,
        status=AttemptStatus.IN_PROGRESS,
        started_at=timezone.now(),
    )
    return redirect("customer:attempt_detail", attempt.pk)
