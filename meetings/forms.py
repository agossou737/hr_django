from django import forms

from employees.forms import StyledFormMixin
from employees.models import Employee

from .models import Meeting, MeetingAction


class MeetingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ["title", "date", "start_time", "end_time", "location", "agenda", "participants"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "agenda": forms.Textarea(attrs={"rows": 4}),
                   "participants": forms.SelectMultiple(attrs={"size": 8})}

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["participants"].queryset = Employee.objects.filter(company=company).exclude(status="left")
        self.fields["participants"].help_text = "Maintenez Ctrl (ou ⌘) pour en sélectionner plusieurs."
        self._style_fields()

    def clean(self):
        d = super().clean()
        if d.get("end_time") and d.get("start_time") and d["end_time"] <= d["start_time"]:
            raise forms.ValidationError("L'heure de fin doit être après l'heure de début.")
        return d


class MinutesForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ["minutes"]
        widgets = {"minutes": forms.Textarea(attrs={"rows": 14})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["minutes"].required = True
        self._style_fields()


class ActionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MeetingAction
        fields = ["description", "owner", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, meeting, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting = meeting
        self.fields["owner"].queryset = meeting.participants.all()
        self._style_fields()
