from django import forms

from employees.forms import CompanyModelForm, StyledFormMixin

from .models import Company, Holiday

WEEKDAYS = [(0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"), (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche")]


class CompanySettingsForm(StyledFormMixin, forms.ModelForm):
    days = forms.MultipleChoiceField(
        label="Jours travaillés", choices=WEEKDAYS, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Company
        fields = [
            "name", "ifu", "rccm", "cnss_number", "address", "city", "phone", "email", "logo",
            "work_start_time", "work_end_time", "late_tolerance_minutes",
            "auto_explanation", "explanation_deadline_days", "fingerprint_self_service",
        ]
        widgets = {
            "work_start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "work_end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["days"].initial = [str(d) for d in sorted(self.instance.work_weekdays)]
        self._style_fields()
        self.fields["days"].widget.attrs.pop("class", None)

    def clean(self):
        data = super().clean()
        start, end = data.get("work_start_time"), data.get("work_end_time")
        if start and end and end <= start:
            raise forms.ValidationError("L'heure de fin doit suivre l'heure de début.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.work_days = ",".join(sorted(self.cleaned_data["days"]))
        if commit:
            obj.save()
        return obj


class HolidayForm(CompanyModelForm):
    class Meta:
        model = Holiday
        fields = ["date", "name"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def clean_date(self):
        date = self.cleaned_data["date"]
        qs = Holiday.objects.filter(company=self.company, date=date)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Un jour férié existe déjà à cette date.")
        return date
