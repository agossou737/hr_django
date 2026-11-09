from django.db import models


class Company(models.Model):
    """Entreprise cliente (tenant). Toutes les données RH lui sont rattachées."""

    name = models.CharField("Raison sociale", max_length=200)
    slug = models.SlugField("Identifiant", unique=True)
    ifu = models.CharField("IFU", max_length=20, blank=True)
    rccm = models.CharField("RCCM", max_length=50, blank=True)
    cnss_number = models.CharField("N° employeur CNSS", max_length=30, blank=True)
    address = models.CharField("Adresse", max_length=255, blank=True)
    city = models.CharField("Ville", max_length=100, blank=True, default="Cotonou")
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    email = models.EmailField("E-mail", blank=True)
    logo = models.ImageField("Logo", upload_to="companies/logos/", blank=True)
    is_active = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CompanyOwnedModel(models.Model):
    """Base abstraite : tout objet appartient à une entreprise."""

    company = models.ForeignKey(
        Company,
        verbose_name="Entreprise",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True
