from django import forms

from employees.forms import CompanyModelForm, StyledFormMixin

from . import services
from .models import LeaveRequest, LeaveType


class LeaveTypeForm(CompanyModelForm):
    class Meta:
        model = LeaveType
        fields = ["name", "annual_days", "is_paid", "needs_approval"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = LeaveType.objects.filter(company=self.company, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ce type existe déjà.")
        return name


class LeaveRequestForm(StyledFormMixin, forms.ModelForm):
    """Formulaire de demande. L'employé est imposé par la vue (jamais choisi par le demandeur)."""

    class Meta:
        model = LeaveRequest
        fields = ["leave_type", "start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company, employee, **kwargs):
        super().__init__(*args, **kwargs)
        self.company, self.employee = company, employee
        self.fields["leave_type"].queryset = LeaveType.objects.filter(company=company)
        self._style_fields()

    def clean(self):
        data = super().clean()
        start, end, leave_type = data.get("start_date"), data.get("end_date"), data.get("leave_type")
        if not (start and end and leave_type):
            return data
        if end < start:
            raise forms.ValidationError("La date de fin précède la date de début.")
        days = services.count_leave_days(self.company, start, end)
        if days <= 0:
            raise forms.ValidationError("Cette période ne contient aucun jour ouvré.")
        if services.has_overlap(self.employee, start, end, exclude_pk=self.instance.pk):
            raise forms.ValidationError("Une demande existe déjà sur tout ou partie de cette période.")
        if leave_type.is_capped:
            used = services.used_days(self.employee, leave_type, start.year)
            if used + days > leave_type.annual_days:
                left = max(leave_type.annual_days - used, 0)
                raise forms.ValidationError(
                    f"Solde insuffisant : {left} jour(s) restant(s) pour « {leave_type.name} » en {start.year}."
                )
        data["days"] = days
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company, obj.employee = self.company, self.employee
        obj.days = self.cleaned_data["days"]
        obj.status = LeaveRequest.Status.PENDING
        if not obj.leave_type.needs_approval:
            obj.status = LeaveRequest.Status.APPROVED
        if commit:
            obj.save()
        return obj


class HRLeaveRequestForm(LeaveRequestForm):
    """Saisie par la RH au nom d'un employé (approuvée directement)."""

    employee_field = forms.ModelChoiceField(label="Employé", queryset=None)

    def __init__(self, *args, company, **kwargs):
        from employees.models import Employee

        super().__init__(*args, company=company, employee=None, **kwargs)
        self.fields["employee_field"].queryset = Employee.objects.filter(company=company).exclude(
            status=Employee.Status.LEFT
        )
        self.order_fields(["employee_field", "leave_type", "start_date", "end_date", "reason"])
        self._style_fields()

    def clean(self):
        self.employee = self.cleaned_data.get("employee_field")
        if self.employee is None:
            return super(LeaveRequestForm, self).clean()
        return super().clean()
