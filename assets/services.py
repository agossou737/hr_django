from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from config.pdfdocs import build_letter_pdf
from notifications.services import notify

from .models import Asset, AssetAssignment


class AssetError(ValueError):
    pass


@transaction.atomic
def assign(asset, employee, user, date, condition="", notes=""):
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if asset.company_id != employee.company_id:
        raise AssetError("Employé et matériel d'entreprises différentes.")
    if asset.status != Asset.Status.AVAILABLE:
        raise AssetError("Ce matériel n'est pas disponible.")
    a = AssetAssignment.objects.create(company=asset.company, asset=asset, employee=employee, assigned_at=date,
                                       condition_out=condition or asset.condition, assigned_by=user, notes=notes)
    asset.status = Asset.Status.ASSIGNED
    asset.save(update_fields=["status"])
    if employee.user_id:
        notify([employee.user], f"Matériel remis : {asset.name}", "Une décharge est disponible dans « Mon matériel ».",
               reverse("assets:mine"))
    return a


@transaction.atomic
def give_back(assignment, date, condition, notes=""):
    if not assignment.is_open:
        raise AssetError("Ce matériel a déjà été restitué.")
    assignment.returned_at, assignment.condition_in = date, condition
    if notes:
        assignment.notes = notes[:255]
    assignment.save(update_fields=["returned_at", "condition_in", "notes"])
    asset = assignment.asset
    asset.condition = condition
    asset.status = Asset.Status.MAINTENANCE if condition == Asset.Condition.POOR else Asset.Status.AVAILABLE
    asset.save(update_fields=["condition", "status"])
    return assignment


def discharge_pdf(a):
    e, s = a.employee, a.asset
    facts = [("Employé", f"{e.full_name} ({e.matricule})"), ("Matériel", s.name), ("Code inventaire", s.tag or "—"),
             ("N° de série", s.serial_number or "—"), ("Valeur", f"{s.value:,.0f} FCFA".replace(",", " ")),
             ("Remis le", f"{a.assigned_at:%d/%m/%Y}"), ("État à la remise", a.get_condition_out_display())]
    paras = ["Je soussigné(e) reconnais avoir reçu le matériel ci-dessus en bon état de fonctionnement, m'engage à "
             "l'utiliser à des fins professionnelles, à en prendre soin et à le restituer à la demande de l'employeur "
             "ou à mon départ de l'entreprise. Toute perte ou dégradation anormale pourra engager ma responsabilité."]
    stamp = ""
    if a.returned_at:
        facts += [("Restitué le", f"{a.returned_at:%d/%m/%Y}"), ("État à la restitution", a.get_condition_in_display())]
        stamp = "MATÉRIEL RESTITUÉ"
    if a.notes:
        paras.append(("Observations", a.notes))
    return build_letter_pdf(a.company, "Décharge de matériel", a.reference, facts, paras,
                            signatures=[("L'employé", e.full_name, "Lu et approuvé"),
                                        ("L'employeur", a.assigned_by.get_full_name() if a.assigned_by else "", "")],
                            stamp=stamp)
