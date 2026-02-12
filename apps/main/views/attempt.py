from collections import defaultdict

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

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

    sections = (
        attempt.exam.sections
        .all()
        .order_by("order")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=Question.objects.order_by("order"),
            )
        )
    )
    ordered_q_ids = []
    for sec in sections:
        ordered_q_ids.extend([q.id for q in sec.questions.all()])

    if not ordered_q_ids:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    qa_qs = QuestionAttempt.objects.filter(section_attempt__attempt=attempt).only("question_id", "is_answered")
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

    sections = (
        attempt.exam.sections
        .all()
        .order_by("order")
        .select_related("material")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=Question.objects.order_by("order").prefetch_related("options"),
            )
        )
    )
    flat_questions = [q for sec in sections for q in sec.questions.all()]
    if not flat_questions:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    q_ids = [q.id for q in flat_questions]
    q_param = request.GET.get("q")
    current_qid = int(q_param) if (q_param and q_param.isdigit() and int(q_param) in q_ids) else q_ids[0]
    qa_qs = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt)
        .select_related("question", "section_attempt")
    )
    qa_by_q_id = {qa.question_id: qa for qa in qa_qs}
    current_qa = qa_by_q_id.get(current_qid)
    if not current_qa:
        ensure_attempt_initialized(attempt)
        current_qa = QuestionAttempt.objects.get(section_attempt__attempt=attempt, question_id=current_qid)
        qa_by_q_id[current_qid] = current_qa

    current_q = current_qa.question
    sa = current_qa.section_attempt
    if sa.status == AttemptStatus.NO_STARTED:
        sa.status = AttemptStatus.IN_PROGRESS
        if not sa.started_at:
            sa.started_at = timezone.now()
        sa.save(update_fields=["status", "started_at"])

    current_section = None
    for sec in sections:
        if sec.id == current_q.section_id:
            current_section = sec
            break

    selected_set = set(
        MCQSelection.objects
        .filter(question_attempt=current_qa)
        .values_list("option_id", flat=True)
    )
    answered_q_ids = {qa.question_id for qa in qa_by_q_id.values() if qa.is_answered}

    idx = q_ids.index(current_qid)
    prev_q_id = q_ids[idx - 1] if idx > 0 else None
    next_q_id = q_ids[idx + 1] if idx < len(q_ids) - 1 else None
    is_last = next_q_id is None

    context = {
        "attempt": attempt,
        "flat_questions": flat_questions,
        "answered_q_ids": answered_q_ids,
        "current_section": current_section,
        "q": current_q,
        "qa": current_qa,
        "selected_set": selected_set,
        "prev_q_id": prev_q_id,
        "next_q_id": next_q_id,
        "q_index": idx + 1,
        "q_total": len(q_ids),
        "is_last": is_last,
    }
    if is_hx(request):
        return render(request, "app/main/attempt/partials/_question_wrapper.html", context)

    return render(request, "app/main/attempt/question.html", context)


# ANSWER SAVE
# ======================================================================================================================
@require_POST
@role_required("customer")
def attempt_answer_view(request, attempt_id: int, question_id: int):
    attempt = load_attempt_for_user(request, attempt_id)

    if attempt.status != AttemptStatus.IN_PROGRESS:
        return redirect("customer:attempt_review", attempt_id=attempt.pk)

    if not is_hx(request):
        return redirect("customer:attempt_detail", attempt_id=attempt.pk)

    q = get_object_or_404(Question.objects.only("id", "question_type", "section_id"), pk=question_id)
    if q.question_type == "mcq_single":
        oid = request.POST.get("option")
        option_ids = [int(oid)] if (oid and oid.isdigit()) else []
        save_mcq_answer_only(attempt, question_id=q.pk, option_ids=option_ids)

    elif q.question_type == "mcq_multi":
        raw = request.POST.getlist("options")
        option_ids = [int(x) for x in raw if x.isdigit()]
        save_mcq_answer_only(attempt, question_id=q.pk, option_ids=option_ids)

    next_q_id = request.POST.get("next_qid")
    next_q_id = int(next_q_id) if (next_q_id and next_q_id.isdigit()) else q.pk

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
    resp["HX-Push-Url"] = reverse(
        "customer:attempt_question",
        args=[attempt.pk]
    ) + f"?q={next_q_id}"

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

    ensure_attempt_initialized(attempt)
    sections = (
        attempt.exam.sections
        .all()
        .order_by("order")
        .select_related("material")
        .prefetch_related(
            Prefetch(
                "questions",
                queryset=(
                    Question.objects
                    .order_by("order")
                    .select_related("speaking_rubric")
                    .prefetch_related("options")
                )
            )
        )
    )
    section_id = request.GET.get("section")
    section_id = int(section_id) if (section_id and section_id.isdigit()) else None
    section_map = {s.id: s for s in sections}
    current_section = section_map.get(section_id) if section_id else (sections[0] if sections else None)

    qa_qs = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt)
        .select_related("question", "section_attempt", "section_attempt__section")
    )
    qa_by_q_id = {qa.question_id: qa for qa in qa_qs}
    section_scores = defaultdict(lambda: {"score": 0.0, "max": 0.0})

    for qa in qa_qs:
        sid = qa.section_attempt.section_id
        section_scores[sid]["score"] += float(qa.score or 0)
        section_scores[sid]["max"] += float(qa.max_score or 0)

    for sec in sections:
        data = section_scores.get(sec.id, {"score": 0.0, "max": 0.0})
        sec.review_score = data["score"]
        sec.review_max = data["max"]

    selections = (
        MCQSelection.objects
        .filter(question_attempt__section_attempt__attempt=attempt)
        .values_list("question_attempt_id", "option_id")
    )
    selected_map = {}
    for qa_id, opt_id in selections:
        selected_map.setdefault(qa_id, set()).add(opt_id)

    correct_map = {}
    for sec in sections:
        for q in sec.questions.all():
            if q.question_type in ("mcq_single", "mcq_multi"):
                correct_map[q.id] = set(
                    q.options.filter(is_correct=True).values_list("id", flat=True)
                )

    writing_map = {
        ws.question_attempt_id: ws
        for ws in (
            WritingSubmission.objects
            .filter(question_attempt__section_attempt__attempt=attempt)
            .select_related("question_attempt")
        )
    }

    for sec in sections:
        for q in sec.questions.all():
            qa = getattr(q, "qa", None)
            if qa:
                q.writing_submission = writing_map.get(qa.id)
            else:
                q.writing_submission = None

    speaking_map = {
        sa.question_attempt_id: sa
        for sa in (
            SpeakingAnswer.objects
            .filter(question_attempt__section_attempt__attempt=attempt)
            .select_related("question_attempt")
        )
    }
    for sec in sections:
        for q in sec.questions.all():
            qa = qa_by_q_id.get(q.id)
            q.qa = qa
            q.speaking_answer = speaking_map.get(qa.pk) if qa else None
            q.writing_submission = writing_map.get(qa.pk) if qa else None

    context = {
        "mode": "review",
        "attempt": attempt,
        "sections": sections,
        "current_section": current_section,
        "qa_by_qid": qa_by_q_id,
        "selected_map": selected_map,
        "correct_map": correct_map,
        "AttemptStatus": AttemptStatus,
    }
    return render(request, "app/main/attempt/review.html", context)