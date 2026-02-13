from collections import defaultdict

from django.db.models import Prefetch
from django.shortcuts import render
from apps.main.services.attempt import ensure_attempt_initialized
from core.models import Question, QuestionAttempt, MCQSelection, AttemptStatus, WritingSubmission, SpeakingAnswer


def _build_review_response(request, attempt, review_url_name):
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
        "review_url_name": review_url_name,
    }
    return render(request, "app/main/attempt/review.html", context)
