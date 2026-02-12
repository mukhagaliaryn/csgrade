import re
from django.utils import timezone
from core.models import Writing, WritingSubmission


def normalize_output(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [re.sub(r"\s+", " ", line).strip() for line in s.split("\n")]
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def grade_writing_submission(submission: WritingSubmission) -> bool:
    writing: Writing = submission.question_attempt.question.writing
    expected = getattr(writing, "expected_output", "") or ""
    user_out = submission.output_text or ""
    is_correct = normalize_output(user_out) == normalize_output(expected)

    submission.is_correct = is_correct
    submission.checked_at = timezone.now()
    submission.save(update_fields=["is_correct", "checked_at"])

    return is_correct
