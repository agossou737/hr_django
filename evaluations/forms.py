from django import forms

from employees.forms import StyledFormMixin

from .models import CRITERIA, SCORE_CHOICES, Evaluation
from .services import evaluable_employees


class EvaluationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ["employee", "period", "date", "strengths", "improvements", "objectives"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "strengths": forms.Textarea(attrs={"rows": 3}),
            "improvements": forms.Textarea(attrs={"rows": 3}),
            "objectives": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["employee"].queryset = evaluable_employees(user)
        for key, label in CRITERIA:
            self.fields[f"score_{key}"] = forms.TypedChoiceField(
                label=label, choices=SCORE_CHOICES, coerce=int, initial=3
            )
            if self.instance.pk and key in self.instance.scores:
                self.fields[f"score_{key}"].initial = self.instance.scores[key]
        self.order_fields(["employee", "period", "date"] + [f"score_{k}" for k, _ in CRITERIA]
                          + ["strengths", "improvements", "objectives"])
        self._style_fields()

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company = self.user.company
        obj.scores = {key: self.cleaned_data[f"score_{key}"] for key, _ in CRITERIA}
        if not obj.pk:
            obj.evaluator = self.user
        if commit:
            obj.save()
        return obj
