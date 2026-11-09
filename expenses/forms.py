import datetime

from django import forms

from config.files import validate_upload
from employees.forms import StyledFormMixin

from .models import ExpenseClaim


class ExpenseForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseClaim
        fields = ["date", "title", "category", "amount", "receipt"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, company, employee, **kwargs):
        super().__init__(*args, **kwargs)
        self.company, self.employee = company, employee
        self._style_fields()

    def clean_amount(self):
        a = self.cleaned_data["amount"]
        if a <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return a

    def clean_date(self):
        d = self.cleaned_data["date"]
        if d > datetime.date.today():
            raise forms.ValidationError("La date ne peut pas être dans le futur.")
        return d

    def clean_receipt(self):
        f = self.cleaned_data.get("receipt")
        if f and hasattr(f, "size"):
            validate_upload(f)
        return f

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company, obj.employee = self.company, self.employee
        if commit:
            obj.save()
        return obj
