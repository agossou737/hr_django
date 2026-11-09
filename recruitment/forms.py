from django import forms

from config.files import validate_upload
from employees.forms import CompanyModelForm

from .models import Application, JobOffer


class JobOfferForm(CompanyModelForm):
    company_scoped_fields = ("department",)

    class Meta:
        model = JobOffer
        fields = ["title", "department", "contract_type", "location", "openings", "closing_date", "status", "description"]
        widgets = {
            "closing_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 5}),
        }


class ApplicationForm(CompanyModelForm):
    company_scoped_fields = ("job",)

    class Meta:
        model = Application
        fields = ["job", "first_name", "last_name", "email", "phone", "cv", "rating", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_cv(self):
        cv = self.cleaned_data.get("cv")
        if cv and hasattr(cv, "size"):
            validate_upload(cv)
        return cv

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not 1 <= rating <= 5:
            raise forms.ValidationError("La note doit être comprise entre 1 et 5.")
        return rating
