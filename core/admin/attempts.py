from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from core.admin import LinkedAdminMixin
from core.models import MCQSelection, SpeakingAnswer, QuestionAttempt, SectionAttempt, ExamAttempt, WritingSubmission


# ======================================================================================================================
# QuestionAttempt
# ======================================================================================================================
# MCQSelectionInline
class MCQSelectionInline(admin.TabularInline):
    model = MCQSelection
    extra = 0


# SpeakingAnswerInline
class SpeakingAnswerInline(admin.StackedInline):
    model = SpeakingAnswer
    extra = 0


# WritingSubmissionInline
class WritingSubmissionInline(admin.StackedInline):
    model = WritingSubmission
    extra = 0


# QuestionAttemptAdmin
@admin.register(QuestionAttempt)
class QuestionAttemptAdmin(LinkedAdminMixin, admin.ModelAdmin):
    list_display = ("question", "section_attempt", "is_answered", "is_graded", "score", "max_score", )
    list_filter = ("is_answered", "is_graded", "question__question_type")
    search_fields = ("question__prompt", )
    readonly_fields = ("attempt_section_link", )

    def attempt_section_link(self, obj):
        return self.parent_link(obj, 'section_attempt')
    attempt_section_link.short_description = _("Секция нәтижесі")

    inlines = (MCQSelectionInline, SpeakingAnswerInline, WritingSubmissionInline, )


# ======================================================================================================================
# SectionAttempt
# ======================================================================================================================
# QuestionAttemptInline
class QuestionAttemptInline(LinkedAdminMixin, admin.TabularInline):
    model = QuestionAttempt
    extra = 0
    readonly_fields = ("detail_link", )

    def detail_link(self, obj):
        return self.admin_link(obj, label=_("Толығырақ"))
    detail_link.short_description = _("Сілтеме")


# SectionAttemptAdmin
@admin.register(SectionAttempt)
class SectionAttemptAdmin(LinkedAdminMixin, admin.ModelAdmin):
    list_display = ("attempt", "section", "status", "score", "max_score", "time_spent_seconds", )
    list_filter = ("status", "section__section_type")
    inlines = (QuestionAttemptInline, )
    readonly_fields = ("attempt_link",)

    def attempt_link(self, obj):
        return self.parent_link(obj, 'attempt')
    attempt_link.short_description = _("Емтихан нәтижесі")


# ======================================================================================================================
# ExamAttempt
# ======================================================================================================================
# SectionAttemptInline
class SectionAttemptInline(LinkedAdminMixin, admin.TabularInline):
    model = SectionAttempt
    extra = 0
    readonly_fields = ("detail_link", )

    def detail_link(self, obj):
        return self.admin_link(obj, label=_("Толығырақ"))
    detail_link.short_description = _("Сілтеме")


# ExamAttemptAdmin
@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "exam", "status", "started_at", "finished_at", "total_score", "max_total_score", )
    list_filter = ("status", "exam")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "exam")
    inlines = (SectionAttemptInline, )
