from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ======================================================================================================================
# Attempts (submission layer)
# ======================================================================================================================
# AttemptStatus
class AttemptStatus(models.TextChoices):
    NO_STARTED = "no_started", "Басталмаған"
    IN_PROGRESS = "in_progress", "Тест өтіп жатыр"
    FINISHED = "finished", "Аяқталды"
    ABORTED = "aborted", "Тоқтатылды"


# ExamAttempt
class ExamAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exam_attempts", verbose_name=_("Пайдаланушы"),
    )
    exam = models.ForeignKey(
        "Exam", on_delete=models.CASCADE,
        related_name="attempts", verbose_name=_("Емтихан"),
    )
    status = models.CharField(_("Статус"), max_length=16, choices=AttemptStatus.choices, default=AttemptStatus.NO_STARTED)
    started_at = models.DateTimeField(_("Басталған уақыты"), default=timezone.now)
    finished_at = models.DateTimeField(_("Аяқталған уақыты"), blank=True, null=True)
    total_score = models.DecimalField(_("Жалпы балл"), max_digits=7, decimal_places=2, default=0)
    max_total_score = models.DecimalField(_("Макс жалпы балл"), max_digits=7, decimal_places=2, default=0)
    meta = models.JSONField(_("Қосымша дерек"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Емтихан нәтижесі")
        verbose_name_plural = _("Емтихан нәтижелері")

    def __str__(self):
        return _('#{}-емтихан нәтижесі').format(self.pk)

    def mark_submitted(self):
        self.status = AttemptStatus.SUBMITTED
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "finished_at"])


# SectionAttempt
class SectionAttempt(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE,
        related_name="section_attempts", verbose_name=_("Емтихан тапсыру"),
    )
    section = models.ForeignKey(
        "Section", on_delete=models.CASCADE,
        related_name="attempts", verbose_name=_("Емтихан секциясы"),
    )
    status = models.CharField(_("Статус"), max_length=16, choices=AttemptStatus.choices, default=AttemptStatus.NO_STARTED)
    started_at = models.DateTimeField(_("Басталған уақыты"), blank=True, null=True)
    finished_at = models.DateTimeField(_("Аяқталған уақыты"), blank=True, null=True)
    score = models.DecimalField(_("Секция баллы"), max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(_("Макс секция баллы"), max_digits=7, decimal_places=2, default=0)
    time_spent_seconds = models.PositiveIntegerField(_("Жұмсаған уақыт (сек)"), default=0)

    class Meta:
        verbose_name = _("Секция нәтижесі")
        verbose_name_plural = _("Секция нәтижелері")

    def __str__(self):
        return _('#{}-секция нәтижесі').format(self.pk)


# QuestionAttempt
class QuestionAttempt(models.Model):
    section_attempt = models.ForeignKey(
        SectionAttempt, on_delete=models.CASCADE,
        related_name="question_attempts", verbose_name=_("Секция тапсыруы"),
    )
    question = models.ForeignKey(
        "Question", on_delete=models.CASCADE,
        related_name="attempts", verbose_name=_("Сұрақ"),
    )
    answer_json = models.JSONField(_("Жауап (JSON)"), default=dict, blank=True)
    score = models.DecimalField(_("Ұпай"), max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(_("Макс ұпай"), max_digits=7, decimal_places=2, default=0)
    is_answered = models.BooleanField(_("Жауап берілді"), default=False)
    is_graded = models.BooleanField(_("Бағаланды"), default=False)
    created_at = models.DateTimeField(_("Құрылған уақыты"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Жаңартылған уақыты"), auto_now=True)

    class Meta:
        verbose_name = _("Сұрақ нәтижесі")
        verbose_name_plural = _("Сұрақ нәтижелері")

    def __str__(self):
        return _('#{}-сұрақ нәтижесі').format(self.pk)


# ======================================================================================================================
# QuestionAttempt answers
# ======================================================================================================================
# SpeakingAnswer
class SpeakingAnswer(models.Model):
    question_attempt = models.OneToOneField(
        "QuestionAttempt", on_delete=models.CASCADE,
        related_name="speaking_answer", verbose_name=_("Сұрақ нәтижесі"),
    )
    audio = models.FileField(_("Аудио жауап"), upload_to="exams/speaking/", blank=True, null=True)
    transcript = models.TextField(_("Транскрипт"), blank=True, null=True)
    matched_count = models.PositiveSmallIntegerField(_("Табылған сөз саны"), default=0)
    matched_keywords = models.JSONField(_("Табылған кілт сөздер"), default=list, blank=True)

    class Meta:
        verbose_name = _("Айтылым жауабы")
        verbose_name_plural = _("Айтылым жауаптары")

    def __str__(self):
        return _('#{}-айтылым жауабы').format(self.pk)


# MCQSelection
class MCQSelection(models.Model):
    question_attempt = models.ForeignKey(
        QuestionAttempt, on_delete=models.CASCADE,
        related_name="mcq_selections", verbose_name=_("Сұрақ нәтижесі"),
    )
    option = models.ForeignKey(
        "Option", on_delete=models.CASCADE,
        related_name="selections", verbose_name=_("Нұсқа"),
    )

    class Meta:
        verbose_name = _("Тест жауабы")
        verbose_name_plural = _("Тест жауаптары")

    def __str__(self):
        return _('#{}-тест жауабы').format(self.pk)


# WritingSubmission
class WritingSubmission(models.Model):
    class Language(models.TextChoices):
        PYTHON = "python", _("Python")
        CPP = "cpp", _("C++")
        JAVA = "java", _("Java")
        JS = "js", _("JavaScript")

    question_attempt = models.OneToOneField(
        QuestionAttempt, on_delete=models.CASCADE,
        related_name="writing_submission", verbose_name=_("Сұрақ нәтижесі"),
    )
    language = models.CharField(_("Тіл"), max_length=16, choices=Language.choices, default=Language.PYTHON)
    code = models.TextField(_("Код"), blank=True, null=True)
    output_text = models.TextField(_("Жауап (output)"), blank=True, null=True)
    is_correct = models.BooleanField(_("Дұрыс"), default=False)
    checked_at = models.DateTimeField(_("Тексерілген уақыты"), blank=True, null=True)

    class Meta:
        verbose_name = _("Жазбаша жауабы")
        verbose_name_plural = _("Жазбаша жауаптары")

    def __str__(self):
        return _('#{}-жазбаша жауабы').format(self.pk)
