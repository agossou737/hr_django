from django.db import models

from companies.models import CompanyOwnedModel


class WebAuthnCredential(CompanyOwnedModel):
    """Clé WebAuthn : la biométrie (empreinte, visage du téléphone, Windows Hello…) reste dans l'appareil,
    le serveur ne conserve qu'une clé publique."""

    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="webauthn_credentials")
    credential_id = models.CharField("Identifiant", max_length=512, unique=True)
    public_key = models.BinaryField("Clé publique")
    sign_count = models.PositiveBigIntegerField("Compteur", default=0)
    label = models.CharField("Appareil", max_length=80, blank=True)
    created_at = models.DateTimeField("Enregistré le", auto_now_add=True)
    last_used_at = models.DateTimeField("Dernière utilisation", null=True, blank=True)

    class Meta:
        verbose_name = "Appareil biométrique"
        verbose_name_plural = "Appareils biométriques"
        ordering = ["employee__last_name", "-created_at"]

    def __str__(self):
        return f"{self.employee.full_name} — {self.label or 'appareil'}"


class FingerprintReader(CompanyOwnedModel):
    """Lecteur d'empreintes USB / terminal : s'authentifie auprès de l'API avec une clé secrète."""

    name = models.CharField("Nom", max_length=100)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    key_prefix = models.CharField("Début de la clé", max_length=8, editable=False)
    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField("Dernière activité", null=True, blank=True)

    class Meta:
        verbose_name = "Lecteur d'empreintes"
        verbose_name_plural = "Lecteurs d'empreintes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ReaderUser(CompanyOwnedModel):
    """Correspondance entre l'identifiant enregistré dans le lecteur et l'employé."""

    employee = models.ForeignKey("employees.Employee", verbose_name="Employé", on_delete=models.CASCADE,
                                 related_name="reader_ids")
    reader_user_id = models.CharField("Identifiant dans le lecteur", max_length=40)

    class Meta:
        verbose_name = "Identifiant de lecteur"
        verbose_name_plural = "Identifiants de lecteur"
        constraints = [models.UniqueConstraint(fields=["company", "reader_user_id"], name="uniq_reader_user_per_company")]

    def __str__(self):
        return f"{self.reader_user_id} → {self.employee.full_name}"
