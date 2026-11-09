from django import forms

from employees.forms import StyledFormMixin
from employees.models import Employee
from explanations.models import Explanation

from .models import Sanction


class SanctionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Sanction
        fields = ["employee", "kind", "date", "reason", "details", "suspension_days", "explanation"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "details": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["employee"].queryset = Employee.objects.filter(company=company).exclude(status="left")
        self.fields["explanation"].queryset = Explanation.objects.filter(company=company).select_related("employee")
        self.fields["explanation"].required = False
        self._style_fields()

    def clean(self):
        d = super().clean()
        exp = d.get("explanation")
        if exp and d.get("employee") and exp.employee_id != d["employee"].pk:
            raise forms.ValidationError("La demande d'explication concerne un autre employé.")
        if d.get("kind") == Sanction.Kind.SUSPENSION and not d.get("suspension_days"):
            raise forms.ValidationError("Indiquez le nombre de jours de mise à pied.")
        return d

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company = self.company
        if commit:
            obj.save()
        return obj
