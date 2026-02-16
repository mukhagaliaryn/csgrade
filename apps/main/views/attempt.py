from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from apps.main.services.review import _build_review_response
from core.utils.decorators import role_required
from django.views.decorators.http import require_GET, require_POST
from apps.main.services.attempt import ensure_attempt_initialized, save_mcq_answer_only, load_attempt_for_user, \
    is_hx, finish_attempt_auto, build_attempt_question_context, grade_pending_open_questions
from core.models import AttemptStatus, Question, QuestionAttempt, MCQSelection, SpeakingAnswer, WritingSubmission


# attempt detail redirect
# ======================================================================================================================
@require_GET
@role_required("customer")
def attempt_detail_view(request, attempt_id: int):
    attempt = load_attempt_for_user(request, attempt_id)
    ensure_attempt_initialized(attempt)

    if attempt.status in (AttemptStatus.FINISHED, AttemptStatus.ABORTED):
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    qa_qs = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt)
        .only("question_id", "is_answered", "order")
        .order_by("order", "id")
    )
    ordered_q_ids = [qa.question_id for qa in qa_qs]
    if not ordered_q_ids:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    answered_q_ids = {qa.question_id for qa in qa_qs if qa.is_answered}
    q_param = request.GET.get("q")
    if q_param and q_param.isdigit() and int(q_param) in ordered_q_ids:
        qid = int(q_param)
    else:
        qid = next((x for x in ordered_q_ids if x not in answered_q_ids), ordered_q_ids[0])

    url = reverse("customer:attempt_question", args=[attempt.pk])
    return redirect(f"{url}?q={qid}")


# ======================================================================================================================
# attempt question page
# ======================================================================================================================
@require_GET
@role_required("customer")
def attempt_question_view(request, attempt_id: int):
    attempt = load_attempt_for_user(request, attempt_id)
    ensure_attempt_initialized(attempt)

    if attempt.status in (AttemptStatus.FINISHED, AttemptStatus.ABORTED):
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    q_param = request.GET.get("q")
    current_qid = int(q_param) if (q_param and q_param.isdigit()) else 0
    ctx = build_attempt_question_context(attempt, current_qid)
    if not ctx:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    sa = ctx["qa"].section_attempt
    if sa.status == AttemptStatus.NO_STARTED:
        sa.status = AttemptStatus.IN_PROGRESS
        if not sa.started_at:
            sa.started_at = timezone.now()
        sa.save(update_fields=["status", "started_at"])

    if is_hx(request):
        return render(request, "app/main/attempt/partials/_question_wrapper.html", ctx)

    return render(request, "app/main/attempt/question.html", ctx)


# ANSWER SAVE
# ======================================================================================================================
@require_POST
@transaction.atomic
@role_required("customer")
def attempt_answer_view(request, attempt_id: int, question_id: int):
    attempt = load_attempt_for_user(request, attempt_id)

    if attempt.status != AttemptStatus.IN_PROGRESS:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    ensure_attempt_initialized(attempt)
    qa = get_object_or_404(
        QuestionAttempt.objects.select_related(
            "question", "section_attempt", "section_attempt__section", "section_material"
        ).prefetch_related("question__options"),
        section_attempt__attempt=attempt,
        question_id=question_id,
    )
    q = qa.question

    if q.question_type not in (q.QuestionType.MCQ_SINGLE, q.QuestionType.MCQ_MULTI):
        return redirect(reverse("customer:attempt_question", args=[attempt.pk]) + f"?q={q.id}")

    selected_ids: list[int] = []
    if q.question_type == q.QuestionType.MCQ_SINGLE:
        opt = request.POST.get("option")
        if opt and str(opt).isdigit():
            selected_ids = [int(opt)]
    else:
        raw = request.POST.getlist("options")
        selected_ids = [int(x) for x in raw if x and str(x).isdigit()]

    save_mcq_answer_only(qa, selected_ids)

    next_q_param = request.POST.get("next_q_id")
    next_q_id: int | None = None

    if next_q_param and str(next_q_param).isdigit():
        cand = int(next_q_param)
        if QuestionAttempt.objects.filter(section_attempt__attempt=attempt, question_id=cand).exists():
            next_q_id = cand

    if next_q_id is None:
        next_qa = (
            QuestionAttempt.objects
            .filter(section_attempt__attempt=attempt, order__gt=qa.order)
            .order_by("order", "id")
            .first()
        )
        next_q_id = next_qa.question_id if next_qa else qa.question_id

    ctx = build_attempt_question_context(attempt, next_q_id)
    if not ctx:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    ctx["saved"] = True
    html = render_to_string(
        "app/main/attempt/partials/_question_wrapper.html",
        ctx,
        request=request,
    )
    resp = HttpResponse(html)
    shown_qid = ctx["q"].id
    resp["HX-Push-Url"] = reverse("customer:attempt_question", args=[attempt.pk]) + f"?q={shown_qid}"
    return resp


# SPEAKING UPLOAD
# ======================================================================================================================
@require_POST
@transaction.atomic
@role_required("customer")
def attempt_speaking_upload_view(request, attempt_id: int, question_id: int):
    attempt = load_attempt_for_user(request, attempt_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    qa = get_object_or_404(
        QuestionAttempt,
        section_attempt__attempt=attempt,
        question_id=question_id
    )
    q = qa.question

    if q.question_type != "speaking_keywords":
        return redirect("customer:attempt_detail", attempt_id=attempt.pk)

    existing = SpeakingAnswer.objects.filter(question_attempt=qa).first()
    if qa.is_answered or (existing and existing.audio):
        if is_hx(request):
            html = render_to_string(
                "app/main/attempt/partials/_question_wrapper.html",
                build_attempt_question_context(attempt, q.id) | {"saved": True, "already_submitted": True},
                request=request,
            )
            resp = HttpResponse(html)
            resp["HX-Push-Url"] = reverse("customer:attempt_question", args=[attempt.pk]) + f"?q={q.id}"
            return resp
        return redirect("customer:attempt_question", attempt_id=attempt.pk)

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return HttpResponseBadRequest("Audio file is required")

    sa, _ = SpeakingAnswer.objects.get_or_create(question_attempt=qa)
    sa.audio = audio_file
    sa.transcript = ""
    sa.matched_keywords = []
    sa.matched_count = 0
    sa.save(update_fields=["audio", "transcript", "matched_keywords", "matched_count"])

    qa.is_answered = True
    qa.is_graded = False
    qa.score = 0
    qa.answer_json = {"type": "speaking_keywords", "submitted": True}
    qa.save(update_fields=["is_answered", "is_graded", "score", "answer_json"])

    if is_hx(request):
        ctx = build_attempt_question_context(attempt, q.id)
        ctx["saved"] = True
        ctx["speaking_submitted"] = True

        html = render_to_string("app/main/attempt/partials/_question_wrapper.html", ctx, request=request)
        resp = HttpResponse(html)
        resp["HX-Push-Url"] = reverse("customer:attempt_question", args=[attempt.pk]) + f"?q={q.id}"
        return resp

    return redirect("customer:attempt_question", attempt_id=attempt.pk)


# WRITING SUBMIT
# ======================================================================================================================
@require_POST
@transaction.atomic
@role_required("customer")
def attempt_writing_submit_view(request, attempt_id: int, question_id: int):
    attempt = load_attempt_for_user(request, attempt_id)

    if attempt.status != AttemptStatus.IN_PROGRESS:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    qa = get_object_or_404(
        QuestionAttempt,
        section_attempt__attempt=attempt,
        question_id=question_id
    )
    if qa.is_answered:
        if is_hx(request):
            ctx = build_attempt_question_context(attempt, qa.question_id)
            ctx["saved"] = True
            html = render_to_string("app/main/attempt/partials/_question_wrapper.html", ctx, request=request)

            resp = HttpResponse(html)
            resp["HX-Push-Url"] = reverse("customer:attempt_question", args=[attempt.pk]) + f"?q={qa.question_id}"
            return resp

        return redirect("customer:attempt_question", attempt_id=attempt.pk)

    output_text = (request.POST.get("output_text") or "").strip()
    code_text = request.POST.get("code") or ""

    if not output_text and not code_text:
        return HttpResponseBadRequest("Empty submission")

    sub, _ = WritingSubmission.objects.get_or_create(question_attempt=qa)
    sub.code = code_text
    sub.output_text = output_text
    sub.save(update_fields=["code", "output_text"])

    qa.is_answered = True
    qa.is_graded = False
    qa.score = 0
    qa.answer_json = {"type": "writing", "submitted": True}
    qa.save(update_fields=["is_answered", "is_graded", "score", "answer_json"])

    if is_hx(request):
        ctx = build_attempt_question_context(attempt, qa.question_id)
        ctx["saved"] = True
        ctx["writing_submitted"] = True

        html = render_to_string("app/main/attempt/partials/_question_wrapper.html", ctx, request=request)

        resp = HttpResponse(html)
        resp["HX-Push-Url"] = reverse("customer:attempt_question", args=[attempt.pk]) + f"?q={qa.question_id}"
        return resp

    return redirect("customer:attempt_question", attempt_id=attempt.pk)


# SUBMIT + REVIEW
# ======================================================================================================================
@require_POST
@role_required("customer")
def attempt_submit_view(request, attempt_id: int):
    attempt = load_attempt_for_user(request, attempt_id)
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    grade_pending_open_questions(attempt)
    finish_attempt_auto(attempt)
    return redirect("customer:attempt_review", attempt_id=attempt.pk)


# ======================================================================================================================
# attempt review page
# ======================================================================================================================
@require_GET
@role_required("customer")
def attempt_review_view(request, attempt_id: int):
    attempt = load_attempt_for_user(request, attempt_id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        return redirect("customer:attempt_detail", attempt_id=attempt.pk)

    return _build_review_response(request, attempt, review_url_name="customer:attempt_review")

