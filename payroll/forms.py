import datetime
import json

from django import forms

from employees.forms import CompanyModelForm, StyledFormMixin

from .models import DEFAULT_BRACKETS, PayrollPeriod, PayrollSettings, PayslipItem


class PeriodForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PayrollPeriod
        fields = ["year", "month"]

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        today = datetime.date.today()
        self.fields["year"].initial, self.fields["month"].initial = today.year, today.month
        self.fields["month"] = forms.ChoiceField(
            label="Mois", choices=[(i + 1, m) for i, m in enumerate(PayrollPeriod.MONTHS)], initial=today.month
        )
        self.fields["year"].min_value = 2000
        self._style_fields()

    def clean_month(self):
        return int(self.cleaned_data["month"])

    def clean_year(self):
        year = self.cleaned_data["year"]
        if not 2000 <= year <= 2100:
            raise forms.ValidationError("Année invalide.")
        return year

    def clean(self):
        data = super().clean()
        if data.get("year") and data.get("month") and PayrollPeriod.objects.filter(
            company=self.company, year=data["year"], month=data["month"]
        ).exists():
            raise forms.ValidationError("Cette période existe déjà.")
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.company = self.company
        if commit:
            obj.save()
        return obj


class PayslipItemForm(CompanyModelForm):
    class Meta:
        model = PayslipItem
        fields = ["kind", "label", "amount", "subject_to_contributions"]

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return amount


class PayrollSettingsForm(StyledFormMixin, forms.ModelForm):
    brackets = forms.CharField(
        label="Barème ITS mensuel", widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Une tranche par ligne : « plafond;taux ». La dernière ligne sans plafond (ex. « ;30 »).",
    )

    class Meta:
        model = PayrollSettings
        fields = [
            "cnss_employee_rate", "cnss_employer_rate", "cnss_family_rate", "cnss_accident_rate", "cnss_ceiling",
            "vps_rate", "its_deducts_cnss", "round_its", "smig",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rows = self.instance.its_brackets or DEFAULT_BRACKETS
        self.fields["brackets"].initial = "\n".join(f"{'' if c is None else c};{r}" for c, r in rows)
        self.order_fields(list(self.Meta.fields) + ["brackets"])
        self._style_fields()

    def clean_brackets(self):
        parsed, last = [], 0
        lines = [l.strip() for l in self.cleaned_data["brackets"].splitlines() if l.strip()]
        if not lines:
            raise forms.ValidationError("Le barème ne peut pas être vide.")
        for n, line in enumerate(lines, 1):
            try:
                ceiling, rate = [p.strip() for p in line.split(";")]
                rate = float(rate.replace(",", "."))
                ceiling = int(ceiling) if ceiling else None
            except ValueError:
                raise forms.ValidationError(f"Ligne {n} invalide : « {line} ».")
            if not 0 <= rate <= 100:
                raise forms.ValidationError(f"Ligne {n} : taux hors limites.")
            if ceiling is None and n != len(lines):
                raise forms.ValidationError("Seule la dernière tranche peut être sans plafond.")
            if ceiling is not None and ceiling <= last:
                raise forms.ValidationError(f"Ligne {n} : les plafonds doivent être croissants.")
            last = ceiling or last
            parsed.append([ceiling, rate])
        if parsed[-1][0] is not None:
            raise forms.ValidationError("La dernière tranche doit être sans plafond.")
        return parsed

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.its_brackets = self.cleaned_data["brackets"]
        if commit:
            obj.save()
        return obj
