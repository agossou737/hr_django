from django import forms

from employees.forms import CompanyModelForm, StyledFormMixin

from . import services
from .models import LeaveRequest, LeaveType, PermissionRequest


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
        fields = ["leave_type", "start_date", "end_date", "reason", "replacement"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company, employee, **kwargs):
        super().__init__(*args, **kwargs)
        self.company, self.employee = company, employee
        self.fields["leave_type"].queryset = LeaveType.objects.filter(company=company)
        from employees.models import Employee

        self.fields["replacement"].queryset = Employee.objects.filter(company=company).exclude(
            status=Employee.Status.LEFT).exclude(pk=getattr(employee, "pk", None))
        self.fields["replacement"].help_text = "Collègue qui assurera votre intérim. Il devra accepter."
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
        repl = data.get("replacement")
        if repl is not None:
            from .models import LeaveRequest as LR

            if LR.objects.filter(employee=repl, status="approved", start_date__lte=end, end_date__gte=start).exists():
                raise forms.ValidationError(f"{repl.full_name} est lui-même en congé sur cette période.")
        data["days"] = days
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company, obj.employee = self.company, self.employee
        obj.days = self.cleaned_data["days"]
        obj.status = LeaveRequest.Status.PENDING
        if not obj.leave_type.needs_approval:
            obj.status = LeaveRequest.Status.APPROVED
        obj.replacement_status = (LeaveRequest.ReplacementStatus.PENDING if obj.replacement_id
                                  else LeaveRequest.ReplacementStatus.NONE)
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
        self.order_fields(["employee_field", "leave_type", "start_date", "end_date", "reason", "replacement"])
        self.fields["replacement"].queryset = self.fields["employee_field"].queryset
        self._style_fields()

    def clean(self):
        self.employee = self.cleaned_data.get("employee_field")
        if self.employee is None:
            return super(LeaveRequestForm, self).clean()
        return super().clean()


class PermissionRequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PermissionRequest
        fields = ["date", "start_time", "end_time", "reason"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company, employee, **kwargs):
        super().__init__(*args, **kwargs)
        self.company, self.employee = company, employee
        self._style_fields()

    def clean(self):
        data = super().clean()
        d, a, b = data.get("date"), data.get("start_time"), data.get("end_time")
        if a and b and b <= a:
            raise forms.ValidationError("L'heure de fin doit être après l'heure de début.")
        if d and self.employee and PermissionRequest.objects.filter(
            employee=self.employee, date=d, status__in=["pending", "approved"],
            start_time__lt=b or a, end_time__gt=a or b,
        ).exists():
            raise forms.ValidationError("Une permission existe déjà sur ce créneau.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company, obj.employee = self.company, self.employee
        if commit:
            obj.save()
        return obj
