from django import forms
from django.contrib.auth import password_validation

from employees.forms import StyledFormMixin
from employees.models import Employee

from .models import User


class _UserBase(StyledFormMixin, forms.ModelForm):
    employee = forms.ModelChoiceField(
        label="Fiche employé liée", queryset=Employee.objects.none(), required=False,
        help_text="Permet à cette personne de voir ses congés, ses bulletins et ses évaluations.",
    )

    def __init__(self, *args, company, acting_user, **kwargs):
        super().__init__(*args, **kwargs)
        self.company, self.acting_user = company, acting_user
        roles = list(User.Role.choices)
        if acting_user.role != User.Role.ADMIN:  # un RH ne crée pas d'administrateur
            roles = [r for r in roles if r[0] != User.Role.ADMIN]
        self.fields["role"].choices = roles
        free = Employee.objects.filter(company=company).exclude(status=Employee.Status.LEFT)
        qs = free.filter(user__isnull=True)
        if self.instance.pk and hasattr(self.instance, "employee"):
            qs = free.filter(pk=self.instance.employee.pk) | qs
            self.fields["employee"].initial = self.instance.employee
        self.fields["employee"].queryset = qs.distinct()
        self._style_fields()

    def _link_employee(self, user):
        employee = self.cleaned_data.get("employee")
        Employee.objects.filter(user=user).exclude(pk=getattr(employee, "pk", None)).update(user=None)
        if employee:
            employee.user = user
            employee.save(update_fields=["user"])


class UserCreateForm(_UserBase):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Confirmation", widget=forms.PasswordInput, strip=False)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet e-mail.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
            else:
                password_validation.validate_password(p1, User(email=data.get("email", "")))
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.company = self.company
        user.set_password(self.cleaned_data["password1"])
        user.save()
        self._link_employee(user)
        return user


class UserUpdateForm(_UserBase):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "role", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk == self.acting_user.pk:  # on ne se retire pas ses propres droits
            self.fields["role"].disabled = True
            self.fields["is_active"].disabled = True
        if self.instance.role == User.Role.ADMIN and self.acting_user.role != User.Role.ADMIN:
            for f in ("role", "is_active", "employee"):
                self.fields[f].disabled = True

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and not self.fields["employee"].disabled:
            self._link_employee(user)
        return user


class PasswordResetForm(StyledFormMixin, forms.Form):
    password1 = forms.CharField(label="Nouveau mot de passe", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Confirmation", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self._style_fields()

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
            else:
                password_validation.validate_password(p1, self.user)
        return data

    def save(self):
        self.user.set_password(self.cleaned_data["password1"])
        self.user.save(update_fields=["password"])
