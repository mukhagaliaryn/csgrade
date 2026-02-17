from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
import random
from apps.main.services.speaking import score_speaking, match_keywords, transcribe_audio
from apps.main.services.writing import grade_writing_submission
from core.models import Question, SpeakingRubric, SectionMaterial
from core.models.attempts import (
    ExamAttempt, SectionAttempt, QuestionAttempt,
    AttemptStatus, MCQSelection, WritingSubmission, SpeakingAnswer,
)


def load_attempt_for_user(request, attempt_id: int) -> ExamAttempt:
    return get_object_or_404(
        ExamAttempt.objects.select_related("exam"),
        pk=attempt_id,
        user=request.user,
    )


def is_hx(request):
    return request.headers.get("HX-Request") == "true"


# ensure_attempt_initialized
@transaction.atomic
def ensure_attempt_initialized(attempt: ExamAttempt) -> None:
    exam = attempt.exam

    if attempt.status == AttemptStatus.NO_STARTED:
        attempt.status = AttemptStatus.IN_PROGRESS
        if not attempt.started_at:
            attempt.started_at = timezone.now()
        attempt.save(update_fields=["status", "started_at"])

    sections = list(exam.sections.all().order_by("order"))

    existing_sa = {
        sa.section_id: sa
        for sa in attempt.section_attempts.select_related("section").all()
    }

    to_create = []
    for sec in sections:
        if sec.id not in existing_sa:
            to_create.append(
                SectionAttempt(
                    attempt=attempt,
                    section=sec,
                    status=AttemptStatus.NO_STARTED,
                    max_score=Decimal(str(sec.max_score or 0)),
                )
            )
    if to_create:
        SectionAttempt.objects.bulk_create(to_create)

    existing_sa = {
        sa.section.section_type: sa
        for sa in attempt.section_attempts.select_related("section").all()
    }

    if QuestionAttempt.objects.filter(section_attempt__attempt=attempt).exists():
        max_total = (
            QuestionAttempt.objects
            .filter(section_attempt__attempt=attempt)
            .aggregate(total=Sum("max_score"))["total"]
            or Decimal("0")
        )
        if attempt.max_total_score != max_total:
            attempt.max_total_score = max_total
            attempt.save(update_fields=["max_total_score"])
        return

    reading_sa = existing_sa.get("reading")
    listening_sa = existing_sa.get("listening")
    speaking_sa = existing_sa.get("speaking")
    writing_sa = existing_sa.get("writing")

    if not all([reading_sa, listening_sa, speaking_sa, writing_sa]):
        return

    reading_mats = list(
        SectionMaterial.objects.filter(section=reading_sa.section, is_active=True).order_by("order", "id")
    )
    listening_mats = list(
        SectionMaterial.objects.filter(section=listening_sa.section, is_active=True).order_by("order", "id")
    )
    if not reading_mats or not listening_mats:
        return

    r_mat = random.choice(reading_mats)
    l_mat = random.choice(listening_mats)

    r_qs = list(
        Question.objects
        .filter(section_material=r_mat)
        .order_by("order", "id")[:10]
    )
    l_qs = list(
        Question.objects
        .filter(section_material=l_mat)
        .order_by("order", "id")[:10]
    )

    speaking_pool = list(
        Question.objects.filter(section=speaking_sa.section).order_by("order", "id")
    )
    if not speaking_pool:
        return
    s_q = random.choice(speaking_pool)

    writing_pool = Question.objects.filter(
        section=writing_sa.section,
        question_type=Question.QuestionType.WRITING
    )
    # 5–9 баллдық шаблон
    TEMPLATE = [5, 6, 7, 8, 9]

    w_qs = []
    for pts in TEMPLATE:
        candidates = list(writing_pool.filter(points=pts))
        if not candidates:
            return

        w_qs.append(random.choice(candidates))

    qa_to_create: list[QuestionAttempt] = []
    order = 1

    def add(sa: SectionAttempt, qs: list[Question], mat=None):
        nonlocal order

        for q in qs:
            option_ids = []

            if q.question_type in (
                    Question.QuestionType.MCQ_SINGLE,
                    Question.QuestionType.MCQ_MULTI,
            ):
                opts = list(q.options.values_list("id", flat=True))
                random.shuffle(opts)
                option_ids = opts

            qa_to_create.append(
                QuestionAttempt(
                    section_attempt=sa,
                    question=q,
                    section_material=mat,
                    order=order,
                    max_score=Decimal(str(q.points or 0)),
                    option_order=option_ids,
                )
            )
            order += 1

    add(reading_sa, r_qs, mat=r_mat)
    add(listening_sa, l_qs, mat=l_mat)
    add(speaking_sa, [s_q], mat=None)
    add(writing_sa, w_qs, mat=None)

    if qa_to_create:
        QuestionAttempt.objects.bulk_create(qa_to_create)

    max_total = sum((qa.max_score or Decimal("0")) for qa in qa_to_create)
    attempt.max_total_score = max_total
    attempt.save(update_fields=["max_total_score"])


# recalc_attempt_scores
def recalc_attempt_scores(attempt: ExamAttempt) -> None:
    for sa in attempt.section_attempts.all():
        agg = sa.question_attempts.aggregate(
            total=Sum("score"),
            max_total=Sum("max_score"),
        )
        s = agg["total"] or Decimal("0")
        ms = agg["max_total"] or Decimal("0")

        updates = []
        if sa.score != s:
            sa.score = s
            updates.append("score")
        if sa.max_score != ms:
            sa.max_score = ms
            updates.append("max_score")
        if updates:
            sa.save(update_fields=updates)

    agg2 = attempt.section_attempts.aggregate(total=Sum("score"), max_total=Sum("max_score"))
    total = agg2["total"] or Decimal("0")
    max_total = agg2["max_total"] or Decimal("0")

    updates = []
    if attempt.total_score != total:
        attempt.total_score = total
        updates.append("total_score")
    if attempt.max_total_score != max_total:
        attempt.max_total_score = max_total
        updates.append("max_total_score")
    if updates:
        attempt.save(update_fields=updates)


# save_mcq_answer_only
@transaction.atomic
def save_mcq_answer_only(qa: QuestionAttempt, selected_ids: list[int]) -> None:
    q = qa.question
    if q.question_type not in (q.QuestionType.MCQ_SINGLE, q.QuestionType.MCQ_MULTI):
        raise ValidationError("save_mcq_answer_only can be used only for MCQ questions.")

    if selected_ids:
        allowed_ids = set(q.options.values_list("id", flat=True))
        if not set(selected_ids).issubset(allowed_ids):
            raise ValidationError("One or more selected options do not belong to this question.")

    MCQSelection.objects.filter(question_attempt=qa).delete()
    if selected_ids:
        MCQSelection.objects.bulk_create(
            [MCQSelection(question_attempt=qa, option_id=oid) for oid in selected_ids]
        )
        qa.is_answered = True
        qa.answer_json = {"selected_option_ids": selected_ids}
    else:
        qa.is_answered = False
        qa.answer_json = {}

    qa.is_graded = False
    if not qa.max_score:
        qa.max_score = Decimal(str(q.points or 0))

    qa.save(update_fields=["is_answered", "answer_json", "is_graded", "max_score", "updated_at"])


# grade_attempt_mcq
@transaction.atomic
def grade_attempt_mcq(attempt) -> None:
    qas = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt, question__question_type__in=["mcq_single", "mcq_multi"])
        .select_related("question")
        .prefetch_related("question__options")
    )

    selected = {}
    for qa_id, opt_id in MCQSelection.objects.filter(question_attempt__in=qas).values_list("question_attempt_id", "option_id"):
        selected.setdefault(qa_id, set()).add(opt_id)

    for qa in qas:
        q = qa.question
        chosen_set = selected.get(qa.pk, set())
        correct_ids = set(q.options.filter(is_correct=True).values_list("id", flat=True))

        score = Decimal("0")
        points = Decimal(str(q.points or 0))

        if q.question_type == "mcq_single":
            if len(chosen_set) == 1 and chosen_set == correct_ids:
                score = points
        elif q.question_type == "mcq_multi":
            if chosen_set == correct_ids and len(correct_ids) > 0:
                score = points

        qa.score = score
        qa.is_graded = True
        qa.save(update_fields=["score", "is_graded"])

    recalc_attempt_scores(attempt)


# finish_attempt_auto
@transaction.atomic
def finish_attempt_auto(attempt: ExamAttempt) -> None:
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return

    grade_attempt_mcq(attempt)

    attempt.status = AttemptStatus.FINISHED
    if not attempt.finished_at:
        attempt.finished_at = timezone.now()
    attempt.save(update_fields=["status", "finished_at"])

    now = attempt.finished_at or timezone.now()
    for sa in attempt.section_attempts.all():
        if not sa.started_at and attempt.started_at:
            sa.started_at = attempt.started_at
        if sa.status != AttemptStatus.FINISHED:
            sa.status = AttemptStatus.FINISHED
        if not sa.finished_at:
            sa.finished_at = now
        sa.save(update_fields=["status", "started_at", "finished_at"])


# build_attempt_question_context
def build_attempt_question_context(attempt, current_qid: int):
    qa_qs = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt)
        .select_related("question", "section_attempt", "section_attempt__section", "section_material")
        .prefetch_related("question__options")
        .order_by("order", "id")
    )

    qa_list = list(qa_qs)
    if not qa_list:
        return None

    q_ids = [qa.question_id for qa in qa_list]

    if current_qid not in q_ids:
        current_qid = q_ids[0]

    idx = q_ids.index(current_qid)
    qa = qa_list[idx]
    q = qa.question
    if qa.option_order:
        options = list(q.options.filter(id__in=qa.option_order))
        options.sort(key=lambda o: qa.option_order.index(o.id))
    else:
        options = list(q.options.all())
    current_material = qa.section_material

    selected_set = set(
        MCQSelection.objects
        .filter(question_attempt=qa)
        .values_list("option_id", flat=True)
    )

    answered_q_ids = {x.question_id for x in qa_list if x.is_answered}
    prev_q_id = q_ids[idx - 1] if idx > 0 else None
    next_q_id = q_ids[idx + 1] if idx < len(q_ids) - 1 else None

    return {
        "attempt": attempt,
        "answered_q_ids": answered_q_ids,
        "q": q,
        "qa": qa,
        "selected_set": selected_set,
        "current_section": qa.section_attempt.section,
        "current_material": current_material,
        "prev_q_id": prev_q_id,
        "next_q_id": next_q_id,
        "q_index": idx + 1,
        "q_total": len(q_ids),
        "is_last": next_q_id is None,
        "flat_questions": [x.question for x in qa_list],
        "ordered_options": options
    }


# grade_pending_open_questions
def grade_pending_open_questions(attempt):
    qa_qs = (
        QuestionAttempt.objects
        .filter(section_attempt__attempt=attempt, is_answered=True, is_graded=False)
        .select_related("question", "section_attempt")
    )

    for qa in qa_qs:
        q = qa.question

        if q.question_type == "speaking_keywords":
            sa = SpeakingAnswer.objects.filter(question_attempt=qa).first()
            if not sa or not sa.audio:
                continue

            rubric = SpeakingRubric.objects.filter(question=q).first()
            if not rubric:
                continue

            transcript = transcribe_audio(sa.audio.path)
            matched = match_keywords(transcript, rubric.keywords)
            points = score_speaking(matched, rubric.point_per_keyword, rubric.max_points)

            sa.transcript = transcript
            sa.matched_keywords = matched
            sa.matched_count = len(matched)
            sa.save(update_fields=["transcript", "matched_keywords", "matched_count"])

            qa.max_score = rubric.max_points
            qa.score = points
            qa.is_graded = True
            qa.answer_json = {
                "type": "speaking_keywords",
                "transcript": transcript,
                "matched_keywords": matched,
            }
            qa.save(update_fields=["max_score", "score", "is_graded", "answer_json"])

        elif q.question_type == "writing":
            sub = WritingSubmission.objects.filter(question_attempt=qa).first()
            if not sub:
                continue

            is_correct = grade_writing_submission(sub)
            qa.score = qa.max_score if is_correct else 0
            qa.is_graded = True
            qa.answer_json = {"type": "writing", "correct": bool(is_correct)}
            qa.save(update_fields=["score", "is_graded", "answer_json"])
