from ckeditor.widgets import CKEditorWidget
from django import forms
from django.core.exceptions import ValidationError
from core.models import Exam, Question, Option, SectionMaterial, SpeakingRubric


# Exam
# ======================================================================================================================
class ExamAdminForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = "__all__"
        widgets = {
            "description": CKEditorWidget(config_name="default"),
        }


# SectionMaterial
# ======================================================================================================================
class SectionMaterialAdminForm(forms.ModelForm):
    class Meta:
        model = SectionMaterial
        fields = "__all__"
        widgets = {
            "text": CKEditorWidget(config_name="default"),
        }


# QuestionAdmin
# ======================================================================================================================
class QuestionAdminForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = "__all__"
        widgets = {
            "prompt": CKEditorWidget(config_name="default"),
        }


# OptionAdmin
# ======================================================================================================================
class OptionAdminForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = "__all__"
        widgets = {
            "text": CKEditorWidget(config_name="default"),
        }


# SpeakingRubricAdminForm
# ======================================================================================================================
class SpeakingRubricAdminForm(forms.ModelForm):
    keywords_text = forms.CharField(
        label="Кілттік сөздер",
        required=False,
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text="""
            Әр жолға біреу. Максимум 9 сөз/фраза. Әр жолға бір кілт сөз жазыңыз. Мысалы: компьютерлік желі
        """
    )

    class Meta:
        model = SpeakingRubric
        fields = ("question", "keywords_text", "point_per_keyword", "max_points")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and isinstance(self.instance.keywords, list):
            self.fields["keywords_text"].initial = "\n".join(self.instance.keywords)

    def clean_keywords_text(self):
        raw = (self.cleaned_data.get("keywords_text") or "").strip()
        if not raw:
            return []

        parts = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(parts) == 1 and "," in parts[0]:
            parts = [p.strip() for p in parts[0].split(",") if p.strip()]

        seen = set()
        keywords = []
        for p in parts:
            k = p.lower()
            if k in seen:
                continue
            seen.add(k)
            keywords.append(p)

        if len(keywords) > SpeakingRubric.max_keywords:
            raise ValidationError(f"Кілттік сөздер саны {SpeakingRubric.max_keywords}-тан аспауы керек.")

        return keywords

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.keywords = self.cleaned_data.get("keywords_text", [])
        if commit:
            obj.full_clean()
            obj.save()
        return obj
