from django import forms

from employees.forms import CompanyModelForm, StyledFormMixin
from employees.models import Employee

from .models import Training


class TrainingForm(CompanyModelForm):
    class Meta:
        model = Training
        fields = ["title", "provider", "start_date", "end_date", "location", "cost", "description"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        d = super().clean()
        if d.get("start_date") and d.get("end_date") and d["end_date"] < d["start_date"]:
            raise forms.ValidationError("La date de fin précède la date de début.")
        return d


class EnrollForm(StyledFormMixin, forms.Form):
    employees = forms.ModelMultipleChoiceField(label="Employés à inscrire", queryset=Employee.objects.none(),
                                               widget=forms.SelectMultiple(attrs={"size": 8}))

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employees"].queryset = Employee.objects.filter(company=company).exclude(status="left")
        self._style_fields()
