from collections import defaultdict
from decimal import Decimal
from django.db.models import Count
from django.shortcuts import render
from core.models import QuestionAttempt, MCQSelection, WritingSubmission, SpeakingAnswer, Option


def _build_review_response(request, attempt, review_url_name: str):
    sections = list(
        attempt.exam.sections.all().order_by("order", "id")
    )
    sa_list = list(
        attempt.section_attempts.select_related("section").all()
    )
    sa_by_section_id = {sa.section_id: sa for sa in sa_list}
    for sec in sections:
        sa = sa_by_section_id.get(sec.id)
        if sa:
            sec.review_score = sa.score or Decimal("0")
            sec.review_max = sa.max_score or Decimal("0")
        else:
            sec.review_score = Decimal("0")
            sec.review_max = Decimal("0")

    if attempt.max_total_score is None:
        attempt.max_total_score = Decimal("0")
    if attempt.total_score is None:
        attempt.total_score = Decimal("0")

    counts_qs = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt)
        .values("section_attempt__section_id")
        .annotate(c=Count("id"))
    )
    section_q_count = {row["section_attempt__section_id"]: row["c"] for row in counts_qs}

    section_param = request.GET.get("section")
    current_section = None
    if section_param and str(section_param).isdigit():
        sid = int(section_param)
        current_section = next((s for s in sections if s.id == sid), None)
    if current_section is None and sections:
        current_section = sections[0]

    current_qas = []
    current_material = None

    if current_section:
        current_qas = list(
            QuestionAttempt.objects
            .filter(
                section_attempt__attempt=attempt,
                section_attempt__section=current_section,
            )
            .select_related(
                "question",
                "section_attempt",
                "section_attempt__section",
                "section_material",
            )
            .prefetch_related("question__options")
            .order_by("order", "id")
        )

        for qa in current_qas:
            if qa.section_material_id:
                current_material = qa.section_material
                break

    qa_by_qid = {qa.question_id: qa for qa in current_qas}

    selected_map = defaultdict(set)
    if current_qas:
        for qa_id, opt_id in (
            MCQSelection.objects
            .filter(question_attempt__in=current_qas)
            .values_list("question_attempt_id", "option_id")
        ):
            selected_map[qa_id].add(opt_id)

    correct_map = defaultdict(set)
    shown_questions = [qa.question for qa in current_qas]
    if shown_questions:
        for qid, oid in (
            Option.objects
            .filter(question__in=shown_questions, is_correct=True)
            .values_list("question_id", "id")
        ):
            correct_map[qid].add(oid)

    speaking_map = {}
    writing_map = {}
    if current_qas:
        speaking_map = {
            sa.question_attempt_id: sa
            for sa in SpeakingAnswer.objects.filter(question_attempt__in=current_qas)
        }
        writing_map = {
            ws.question_attempt_id: ws
            for ws in WritingSubmission.objects.filter(question_attempt__in=current_qas)
        }

    sections_raw = sections
    wanted = ["reading", "listening", "speaking", "writing"]
    rank = {t: i for i, t in enumerate(wanted)}
    sections = sorted(
        sections_raw,
        key=lambda s: (rank.get(s.section_type, 999), getattr(s, "order", 0), s.id)
    )

    ctx = {
        "attempt": attempt,
        "mode": "review",
        "review_url_name": review_url_name,
        "sections": sections,
        "section_q_count": section_q_count,
        "current_section": current_section,
        "current_qas": current_qas,
        "current_material": current_material,
        "qa_by_qid": qa_by_qid,
        "selected_map": selected_map,
        "correct_map": correct_map,
        "speaking_map": speaking_map,
        "writing_map": writing_map,
    }
    return render(request, "app/main/attempt/review.html", ctx)