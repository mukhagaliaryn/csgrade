from django.contrib import admin
from django.contrib.admin import register
from django.utils.safestring import mark_safe
from core.admin._mixins import LinkedAdminMixin
from core.forms.exams import ExamAdminForm, SectionMaterialAdminForm, QuestionAdminForm, OptionAdminForm, \
    SpeakingRubricAdminForm
from core.models import Exam, Section, SectionMaterial, Question, Option, SpeakingRubric, Writing
from django.utils.translation import gettext_lazy as _


# ======================================================================================================================
# Exam
# ======================================================================================================================
# SectionInline
class SectionInline(LinkedAdminMixin, admin.TabularInline):
    model = Section
    extra = 0
    fields = ("order", "section_type", "max_score", "time_limit", "detail_link", )
    readonly_fields = ("detail_link", )

    def detail_link(self, obj):
        return self.admin_link(obj, label=_("Толығырақ"))
    detail_link.short_description = _("Сілтеме")


# ExamAdmin
@register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "created_at", )
    list_filter = ("is_published", )
    search_fields = ("title", )
    form = ExamAdminForm

    inlines = (SectionInline, )


# ======================================================================================================================
# Section
# ======================================================================================================================
# SectionMaterialInline
class SectionMaterialInline(LinkedAdminMixin, admin.StackedInline):
    model = SectionMaterial
    extra = 0
    form = SectionMaterialAdminForm


# QuestionInline
class QuestionInline(LinkedAdminMixin, admin.TabularInline):
    model = Question
    fields = ("order", "question_type", "points", "detail_link", )
    extra = 0
    readonly_fields = ("detail_link", )

    def detail_link(self, obj):
        return self.admin_link(obj, label=_("Толығырақ"))
    detail_link.short_description = _("Сілтеме")


# SectionAdmin
@register(Section)
class SectionAdmin(LinkedAdminMixin, admin.ModelAdmin):
    list_display = ("section_type", "max_score", )
    list_filter = ("section_type", )
    readonly_fields = ("exam_link", )

    def exam_link(self, obj):
        return self.parent_link(obj, 'exam')
    exam_link.short_description = _("Емтихан")

    inlines = (SectionMaterialInline, QuestionInline, )

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if obj is None:
            return []

        if obj.section_type in (
                Section.SectionType.LISTENING,
                Section.SectionType.READING,
        ):
            return inline_instances

        return [inl for inl in inline_instances if inl.__class__ is not SectionMaterialInline]


# ======================================================================================================================
# Question
# ======================================================================================================================
# OptionInline
class OptionInline(admin.TabularInline):
    model = Option
    extra = 0
    form = OptionAdminForm


# SpeakingRubricInline
class SpeakingRubricInline(admin.StackedInline):
    model = SpeakingRubric
    extra = 0
    form = SpeakingRubricAdminForm


# WritingInline
class WritingInline(admin.StackedInline):
    model = Writing
    extra = 0


# QuestionAdmin
@admin.register(Question)
class QuestionAdmin(LinkedAdminMixin, admin.ModelAdmin):
    list_display = ("preview", "section", "question_type", "points")
    list_filter = ("question_type", "section__section_type", "section__exam")
    search_fields = ("prompt", "section__exam__title")
    readonly_fields = ("section_link",)
    form = QuestionAdminForm

    def preview(self, obj):
        html = obj.prompt or ''
        return mark_safe(f"<div class='preview'>{html}</div>")

    def section_link(self, obj):
        return self.parent_link(obj, "section")
    section_link.short_description = _("Емтихан")

    inlines = (OptionInline, WritingInline, SpeakingRubricInline, )

    def get_inline_instances(self, request, obj=None):
        inline_instances = super().get_inline_instances(request, obj)
        if obj is None:
            return []

        qt = obj.question_type

        allowed = set()

        if qt in (Question.QuestionType.MCQ_SINGLE, Question.QuestionType.MCQ_MULTI):
            allowed.add(OptionInline)
        if qt == Question.QuestionType.SPEAKING_KEYWORDS:
            allowed.add(SpeakingRubricInline)
        if qt == Question.QuestionType.WRITING:
            allowed.add(WritingInline)

        return [inl for inl in inline_instances if inl.__class__ in allowed]
