from django import forms

from .models import Contract, Department, Employee, Position

INPUT = (
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm "
    "focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
)


class StyledFormMixin:
    """Applique les classes Tailwind à tous les champs."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-slate-300")
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", "text-sm")
            else:
                widget.attrs.setdefault("class", INPUT)


class CompanyModelForm(StyledFormMixin, forms.ModelForm):
    """ModelForm lié à une entreprise : filtre les listes déroulantes et fixe company."""

    company_scoped_fields = ()

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        for name in self.company_scoped_fields:
            self.fields[name].queryset = self.fields[name].queryset.filter(company=company)
        self._style_fields()

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company = self.company
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class DepartmentForm(CompanyModelForm):
    company_scoped_fields = ("head",)

    class Meta:
        model = Department
        fields = ["name", "description", "head"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Department.objects.filter(company=self.company, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ce département existe déjà.")
        return name


class PositionForm(CompanyModelForm):
    company_scoped_fields = ("department",)

    class Meta:
        model = Position
        fields = ["title", "department", "base_salary"]

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        qs = Position.objects.filter(company=self.company, title__iexact=title)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ce poste existe déjà.")
        return title


class EmployeeForm(CompanyModelForm):
    company_scoped_fields = ("department", "position", "manager")

    class Meta:
        model = Employee
        fields = [
            "photo", "matricule", "first_name", "last_name", "gender", "birth_date",
            "birth_place", "nationality", "marital_status", "dependents",
            "email", "phone", "address", "emergency_contact_name", "emergency_contact_phone",
            "cnss_number", "ifu", "department", "position", "manager",
            "hire_date", "exit_date", "status",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hire_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "exit_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        help_texts = {"matricule": "Laissez vide pour une génération automatique (EMP0001…)."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["manager"].queryset = self.fields["manager"].queryset.exclude(
                pk=self.instance.pk
            )

    def clean_matricule(self):
        matricule = self.cleaned_data["matricule"].strip()
        if matricule:
            qs = Employee.objects.filter(company=self.company, matricule=matricule)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Ce matricule est déjà utilisé.")
        return matricule

    def clean(self):
        cleaned = super().clean()
        hire, exit_ = cleaned.get("hire_date"), cleaned.get("exit_date")
        if hire and exit_ and exit_ < hire:
            self.add_error("exit_date", "La date de sortie précède la date d'embauche.")
        return cleaned


class ContractForm(CompanyModelForm):
    class Meta:
        model = Contract
        fields = [
            "contract_type", "start_date", "end_date", "base_salary",
            "weekly_hours", "trial_period_months", "is_current", "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La date de fin précède la date de début.")
        if cleaned.get("contract_type") == Contract.ContractType.CDD and not end:
            self.add_error("end_date", "Un CDD doit avoir une date de fin.")
        return cleaned
