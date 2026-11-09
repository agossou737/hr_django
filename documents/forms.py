from django import forms

from config.files import validate_upload
from employees.forms import CompanyModelForm

from .models import EmployeeDocument


class DocumentForm(CompanyModelForm):
    company_scoped_fields = ("employee",)

    class Meta:
        model = EmployeeDocument
        fields = ["employee", "kind", "title", "file", "issue_date", "expiry_date"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "expiry_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean_file(self):
        file = self.cleaned_data["file"]
        if hasattr(file, "size"):  # nouveau fichier téléversé
            validate_upload(file)
        return file

    def clean(self):
        data = super().clean()
        issue, expiry = data.get("issue_date"), data.get("expiry_date")
        if issue and expiry and expiry < issue:
            raise forms.ValidationError("La date d'expiration précède la date d'émission.")
        return data
