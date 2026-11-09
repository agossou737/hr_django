import datetime

from django import forms

from employees.forms import CompanyModelForm, StyledFormMixin
from employees.models import Employee

from .models import Asset


class AssetForm(CompanyModelForm):
    class Meta:
        model = Asset
        fields = ["name", "tag", "category", "serial_number", "purchase_date", "value", "condition", "notes"]
        widgets = {"purchase_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "notes": forms.Textarea(attrs={"rows": 3})}

    def clean_tag(self):
        tag = self.cleaned_data["tag"].strip()
        qs = Asset.objects.filter(company=self.company, tag=tag) if tag else Asset.objects.none()
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ce code inventaire existe déjà.")
        return tag


class AssignForm(StyledFormMixin, forms.Form):
    employee = forms.ModelChoiceField(label="Employé", queryset=Employee.objects.none())
    assigned_at = forms.DateField(label="Date de remise", initial=datetime.date.today,
                                  widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    notes = forms.CharField(label="Observations", required=False, max_length=255)

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = Employee.objects.filter(company=company).exclude(status="left")
        self._style_fields()


class ReturnForm(StyledFormMixin, forms.Form):
    returned_at = forms.DateField(label="Date de restitution", initial=datetime.date.today,
                                  widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    condition = forms.ChoiceField(label="État à la restitution", choices=Asset.Condition.choices, initial="good")
    notes = forms.CharField(label="Observations", required=False, max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
