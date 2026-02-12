from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


# ======================================================================================================================
# Exam models
# ======================================================================================================================
# Exam
class Exam(models.Model):
    title = models.CharField(_("Тақырыбы"), max_length=255)
    description = models.TextField(_("Анықтама"), blank=True, null=True)
    is_published = models.BooleanField(_("Ашық емтихан"), default=True)
    created_at = models.DateTimeField(_("Жасалған уақыты"), auto_now_add=True)

    class Meta:
        verbose_name = _("Емтихан")
        verbose_name_plural = _("Емтихандар")

    def __str__(self):
        return self.title


# Section
# ======================================================================================================================
class Section(models.Model):
    class SectionType(models.TextChoices):
        LISTENING = "listening", _("Тыңдалым (Listening)")
        READING = "reading", _("Оқылым (Reading)")
        SPEAKING = "speaking", _("Айтылым (Speaking)")
        WRITING = "writing", _("Жазылым (Writing/Practical)")

    exam = models.ForeignKey(
        Exam, related_name="sections",
        on_delete=models.CASCADE, verbose_name=_("Емтихан")
    )
    section_type = models.CharField(
        _("Секция түрі"), max_length=32,
        choices=SectionType.choices, default=SectionType.LISTENING
    )
    max_score = models.PositiveSmallIntegerField(_("Макс. баллы"), default=0)
    time_limit = models.PositiveSmallIntegerField(_("Уақыты (мин)"), default=0)
    order = models.PositiveSmallIntegerField(_("Реттілік"), default=1)

    class Meta:
        verbose_name = _("Секция")
        verbose_name_plural = _("Секциялар")

    def __str__(self):
        return self.get_section_type_display()


# SectionMaterial
# ======================================================================================================================
class SectionMaterial(models.Model):
    section = models.OneToOneField(
        Section, on_delete=models.CASCADE,
        related_name="material", verbose_name=_("Секция")
    )
    text = models.TextField(_("Мәтін"), blank=True, null=True)
    audio = models.FileField(_("Аудиожазба"), upload_to="exams/sounds/", blank=True, null=True)
    time_limit_seconds = models.PositiveSmallIntegerField(_("Уақыты (сек)"), default=0)

    class Meta:
        verbose_name = _("Секция материалы")
        verbose_name_plural = _("Секция материалдары")

    def __str__(self):
        return f"#{self.pk}: {self.section.get_section_type_display()}"


# Question
# ======================================================================================================================
class Question(models.Model):
    class QuestionType(models.TextChoices):
        MCQ_SINGLE = "mcq_single", _("Бір жауапты")
        MCQ_MULTI = "mcq_multi", _("Көп жауапты")
        SPEAKING_KEYWORDS = "speaking_keywords", _("Айтылым")
        WRITING = "writing", _("Жазбаша")

    section = models.ForeignKey(
        Section, on_delete=models.CASCADE,
        related_name="questions", verbose_name=_("Секция")
    )
    question_type = models.CharField(_("Сұрақ типі"), max_length=32, choices=QuestionType.choices)
    prompt = models.TextField(_("Берілгені"))
    points = models.PositiveSmallIntegerField(_("Ұпай"), default=1)
    order = models.PositiveSmallIntegerField(_("Реттілік"), default=1)

    def __str__(self):
        return _('#{}-сұрақ').format(self.pk)

    def clean(self):
        super().clean()
        allowed = {
            self.section.SectionType.LISTENING: {self.QuestionType.MCQ_SINGLE, self.QuestionType.MCQ_MULTI},
            self.section.SectionType.READING:   {self.QuestionType.MCQ_SINGLE, self.QuestionType.MCQ_MULTI},
            self.section.SectionType.SPEAKING:  {self.QuestionType.SPEAKING_KEYWORDS},
            self.section.SectionType.WRITING: {self.QuestionType.WRITING},
        }

        st = self.section.section_type if self.section.pk else None
        if st and self.question_type and self.question_type not in allowed.get(st, set()):
            raise ValidationError({
                "question_type": _("Бұл секцияға бұл сұрақ типін қоюға болмайды.")
            })

    class Meta:
        verbose_name = _("Сұрақ")
        verbose_name_plural = _("Сұрақтар")


# ======================================================================================================================
# Question type
# ======================================================================================================================
# Option
class Option(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE,
        related_name="options", verbose_name=_("Сұрақ")
    )
    text = models.TextField(_("Жауап"))
    is_correct = models.BooleanField(_("Дұрыс жауап"), default=False)

    def __str__(self):
        return _('#{}-нұсқа').format(self.pk)

    class Meta:
        verbose_name = _("Нұсқа")
        verbose_name_plural = _("Нұсқалар")


# Speaking
# ======================================================================================================================
class SpeakingRubric(models.Model):
    question = models.OneToOneField(
        "Question", on_delete=models.CASCADE,
        related_name="speaking_rubric", verbose_name=_("Сұрақ"),
    )
    keywords = models.JSONField(_("Кілттік сөздер"), default=list, blank=True)
    point_per_keyword = models.PositiveSmallIntegerField(_("Әр сөзге балл"), default=3)
    max_points = models.PositiveSmallIntegerField(_("Максимум балл"), default=25)

    max_keywords = 9

    class Meta:
        verbose_name = _("Айтылым рубрикасы")
        verbose_name_plural = _("Айтылым рубрикалары")

    def clean(self):
        super().clean()

        if self.question_id and self.question.question_type != "speaking_keywords":
            raise ValidationError(_("SpeakingRubric тек Speaking сұрағына ғана байланысады."))

        if self.keywords is None:
            self.keywords = []
        if not isinstance(self.keywords, list):
            raise ValidationError({"keywords": _("Кілттік сөздер тізім (list) болуы керек.")})

        cleaned = []
        seen = set()
        for k in self.keywords:
            if not isinstance(k, str):
                continue
            s = k.strip()
            if not s:
                continue
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(s)

        if len(cleaned) > self.max_keywords:
            raise ValidationError({"keywords": _(f"Кілттік сөздер саны {self.max_keywords}-тан аспауы керек.")})

        self.keywords = cleaned

    def __str__(self):
        return _('#{}-рубрика').format(self.pk)


# Writing
# ======================================================================================================================
class Writing(models.Model):
    question = models.OneToOneField(
        Question, on_delete=models.CASCADE,
        related_name="writing", verbose_name=_("Сұрақ")
    )
    expected_output = models.TextField(_("Дұрыс шығару (output)"))
    ignore_whitespace = models.BooleanField(_("Whitespace елемеу"), default=True)

    class Meta:
        verbose_name = _("Жазбаша есеп")
        verbose_name_plural = _("Жазбаша есептер")

    def __str__(self):
        return _('#{}-жазбаша есеп').format(self.pk)