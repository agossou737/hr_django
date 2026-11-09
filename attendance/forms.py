from django import forms
from django.utils import timezone

from employees.forms import CompanyModelForm

from .models import AttendanceRecord

DATETIME_LOCAL = "%Y-%m-%dT%H:%M"


class AttendanceRecordForm(CompanyModelForm):
    """Saisie ou correction manuelle d'un pointage par le service RH."""

    company_scoped_fields = ("employee",)

    class Meta:
        model = AttendanceRecord
        fields = ["employee", "check_in", "check_out", "note"]
        widgets = {
            "check_in": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
            "check_out": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("check_in", "check_out"):
            self.fields[name].input_formats = [DATETIME_LOCAL, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        if self.instance.pk:
            self.fields["employee"].disabled = True
            for name in ("check_in", "check_out"):
                value = getattr(self.instance, name)
                if value:
                    self.initial[name] = timezone.localtime(value).strftime(DATETIME_LOCAL)

    def clean(self):
        cleaned = super().clean()
        check_in, check_out = cleaned.get("check_in"), cleaned.get("check_out")
        employee = cleaned.get("employee") or getattr(self.instance, "employee", None)
        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out", "Le départ doit être postérieur à l'arrivée.")
        if check_in and employee:
            day = timezone.localtime(check_in).date()
            duplicate = AttendanceRecord.objects.filter(employee=employee, date=day)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error("check_in", "Un pointage existe déjà pour cet employé à cette date.")
        return cleaned

    def save(self, commit=True):
        record = super().save(commit=False)
        record.date = timezone.localtime(record.check_in).date()
        record.source_in = AttendanceRecord.Source.MANUAL
        record.source_out = AttendanceRecord.Source.MANUAL if record.check_out else ""
        if commit:
            record.save()
        return record
