from django import forms

from employees.forms import StyledFormMixin
from employees.models import Employee

from .models import Explanation


class AnswerForm(StyledFormMixin, forms.Form):
    answer = forms.CharField(label="Votre explication", min_length=5, widget=forms.Textarea(attrs={"rows": 6}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class DecisionForm(StyledFormMixin, forms.Form):
    comment = forms.CharField(label="Commentaire", max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class ExplanationRequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Explanation
        fields = ["employee", "kind", "date", "subject", "message"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["employee"].queryset = Employee.objects.filter(company=company).exclude(status="left")
        self._style_fields()
