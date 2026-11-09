from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class HRRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Réservé aux rôles Administrateur et Responsable RH rattachés à une entreprise."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.company_id is not None and user.can_manage_hr


class CompanyQuerysetMixin:
    """Isole les données : on ne voit que celles de l'entreprise de l'utilisateur."""

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class CompanyFormMixin:
    """Injecte l'entreprise dans le formulaire et force le rattachement à la sauvegarde."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs


class KioskRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Accès à la borne de pointage : compte « borne », Responsable RH ou Administrateur."""

    def test_func(self):
        user = self.request.user
        return (
            user.is_authenticated
            and user.company_id is not None
            and user.role in (user.Role.KIOSK, user.Role.HR, user.Role.ADMIN)
        )
