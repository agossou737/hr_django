from django import forms

from accounts.models import User
from companies.models import Company
from employees.forms import StyledFormMixin


class CompanyCreateForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="Raison sociale", max_length=200)
    city = forms.CharField(label="Ville", max_length=100, initial="Cotonou", required=False)
    phone = forms.CharField(label="Téléphone", max_length=30, required=False)
    email = forms.EmailField(label="E-mail de l'entreprise", required=False)
    admin_email = forms.EmailField(label="E-mail de l'administrateur")
    admin_first_name = forms.CharField(label="Prénoms de l'administrateur", max_length=150, required=False)
    admin_last_name = forms.CharField(label="Nom de l'administrateur", max_length=150, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_admin_email(self):
        email = self.cleaned_data["admin_email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet e-mail.")
        return email


class CompanyEditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "ifu", "rccm", "cnss_number", "address", "city", "phone", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class AdminUserForm(StyledFormMixin, forms.Form):
    """Nouvel administrateur d'une entreprise ou nouveau super-administrateur de la plateforme."""

    email = forms.EmailField(label="E-mail")
    first_name = forms.CharField(label="Prénoms", max_length=150, required=False)
    last_name = forms.CharField(label="Nom", max_length=150, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet e-mail.")
        return email
