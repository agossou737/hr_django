"""Import en masse des employés depuis un fichier Excel (.xlsx) ou CSV."""
import csv
import datetime
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import Contract, Department, Employee, Position

MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024

# clé interne -> (libellé du modèle, synonymes acceptés dans l'en-tête, normalisés)
COLUMNS = [
    ("matricule", "Matricule", ["matricule", "id"]),
    ("last_name", "Nom*", ["nom", "nom de famille"]),
    ("first_name", "Prénoms*", ["prenoms", "prenom"]),
    ("gender", "Sexe* (M/F)", ["sexe", "genre"]),
    ("hire_date", "Date d'embauche*", ["date d embauche", "embauche", "date embauche"]),
    ("birth_date", "Date de naissance", ["date de naissance", "naissance"]),
    ("birth_place", "Lieu de naissance", ["lieu de naissance"]),
    ("nationality", "Nationalité", ["nationalite"]),
    ("marital_status", "Situation matrimoniale", ["situation matrimoniale", "situation familiale"]),
    ("dependents", "Enfants à charge", ["enfants a charge", "enfants", "nombre d enfants a charge"]),
    ("email", "E-mail", ["email", "e mail", "courriel"]),
    ("phone", "Téléphone", ["telephone", "tel", "mobile"]),
    ("address", "Adresse", ["adresse"]),
    ("emergency_contact_name", "Contact d'urgence", ["contact d urgence", "contact urgence"]),
    ("emergency_contact_phone", "Tél. d'urgence", ["tel d urgence", "telephone d urgence", "tel urgence"]),
    ("cnss_number", "N° CNSS", ["n cnss", "numero cnss", "cnss"]),
    ("ifu", "IFU", ["ifu"]),
    ("department", "Département", ["departement", "service"]),
    ("position", "Poste", ["poste", "fonction"]),
    ("status", "Statut", ["statut"]),
    ("base_salary", "Salaire de base (FCFA)", ["salaire de base fcfa", "salaire de base", "salaire"]),
    ("contract_type", "Type de contrat", ["type de contrat", "contrat"]),
]
HEADERS = [c[1] for c in COLUMNS]
REQUIRED = ["last_name", "first_name", "gender", "hire_date"]
EXAMPLE = ["", "DOSSOU", "Jean", "M", "02/03/2026", "15/06/1990", "Cotonou", "Béninoise", "Marié(e)", 2,
           "jean.dossou@exemple.bj", "+22997000000", "Cotonou, Akpakpa", "Marie DOSSOU", "+22996000000",
           "", "", "Comptabilité", "Comptable", "Actif", 250000, "CDI"]


def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


SYNONYMS = {}
for key, label, names in COLUMNS:
    SYNONYMS[norm(label.replace("*", ""))] = key
    for n in names:
        SYNONYMS[norm(n)] = key

GENDERS = {"m": "M", "h": "M", "masculin": "M", "homme": "M", "f": "F", "feminin": "F", "femme": "F"}
MARITAL = {norm(l): v for v, l in Employee.MaritalStatus.choices}
MARITAL.update({"celibataire": "single", "marie": "married", "divorce": "divorced", "veuf": "widowed", "veuve": "widowed"})
STATUSES = {norm(l): v for v, l in Employee.Status.choices}
STATUSES.update({"actif": "active", "en conge": "on_leave", "suspendu": "suspended", "sorti": "left"})
CONTRACTS = {norm(l): v for v, l in Contract.ContractType.choices}
CONTRACTS.update({"stage": "internship", "prestation": "consultant", "consultant": "consultant", "apprentissage": "apprentice"})


class ImportFileError(Exception):
    pass


def template_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Employés"
    ws.append(HEADERS)
    ws.append(EXAMPLE)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="4F46E5")
    for i, h in enumerate(HEADERS):
        ws.column_dimensions[chr(65 + i)].width = max(16, len(h) + 4)
    help_ws = wb.create_sheet("Aide")
    for line in [
        "Colonnes marquées * obligatoires. La ligne d'exemple (ligne 2) peut être remplacée ou supprimée.",
        "Dates : JJ/MM/AAAA ou AAAA-MM-JJ. Sexe : M ou F.",
        "Situation : Célibataire, Marié(e), Divorcé(e), Veuf/Veuve. Statut : Actif, En congé, Suspendu, Sorti.",
        "Type de contrat : CDI, CDD, Stage, Prestation, Apprentissage (par défaut CDI si un salaire est renseigné).",
        "Département et poste inexistants sont créés automatiquement.",
        "Matricule vide = généré automatiquement. Matricule existant = ligne ignorée (ou mise à jour si l'option est cochée).",
        f"Maximum {MAX_ROWS} lignes par fichier.",
    ]:
        help_ws.append([line])
    help_ws.column_dimensions["A"].width = 120
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def read_rows(uploaded):
    """Retourne (liste de dicts clé→valeur brute, numéros de ligne). Lève ImportFileError."""
    if uploaded.size > MAX_BYTES:
        raise ImportFileError("Fichier trop volumineux (5 Mo maximum).")
    name = uploaded.name.lower()
    raw = uploaded.read()
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        try:
            ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
            table = [list(r) for r in ws.iter_rows(values_only=True)]
        except Exception:
            raise ImportFileError("Fichier Excel illisible.")
    elif name.endswith((".csv", ".txt")):
        text = raw.decode("utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";"
        table = list(csv.reader(io.StringIO(text), dialect))
    else:
        raise ImportFileError("Format non pris en charge : utilisez .xlsx ou .csv.")
    table = [r for r in table if any(str(c).strip() for c in r if c is not None)]
    if not table:
        raise ImportFileError("Le fichier est vide.")
    header = [SYNONYMS.get(norm(h)) for h in table[0]]
    if not set(REQUIRED) <= set(header):
        missing = [dict((k, l) for k, l, _ in COLUMNS)[k] for k in REQUIRED if k not in header]
        raise ImportFileError("Colonnes obligatoires absentes : " + ", ".join(missing) + ". Téléchargez le modèle.")
    body = table[1:]
    if len(body) > MAX_ROWS:
        raise ImportFileError(f"Trop de lignes ({len(body)}) : {MAX_ROWS} maximum par fichier.")
    rows = []
    for i, r in enumerate(body, start=2):
        rows.append((i, {k: (r[j] if j < len(r) else None) for j, k in enumerate(header) if k}))
    return rows


def parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date invalide « {text} »")


def _text(v, maxlen):
    s = "" if v is None else str(v).strip()
    if isinstance(v, float) and v.is_integer():
        s = str(int(v))
    if len(s) > maxlen:
        raise ValueError(f"valeur trop longue ({maxlen} caractères max)")
    return s


def clean_row(raw):
    """Valide une ligne. Retourne (données nettoyées JSON-compatibles, liste d'erreurs)."""
    errors, d = [], {}

    def attempt(label, fn):
        try:
            return fn()
        except ValueError as exc:
            errors.append(f"{label} : {exc}")

    d["last_name"] = attempt("Nom", lambda: _text(raw.get("last_name"), 120)) or ""
    d["first_name"] = attempt("Prénoms", lambda: _text(raw.get("first_name"), 120)) or ""
    if not d["last_name"]:
        errors.append("Nom obligatoire")
    if not d["first_name"]:
        errors.append("Prénoms obligatoires")
    g = norm(raw.get("gender"))
    d["gender"] = GENDERS.get(g, "")
    if not d["gender"]:
        errors.append("Sexe obligatoire (M ou F)")
    hire = attempt("Date d'embauche", lambda: parse_date(raw.get("hire_date")))
    if hire is None and not any("Date d'embauche" in e for e in errors):
        errors.append("Date d'embauche obligatoire")
    d["hire_date"] = hire.isoformat() if hire else None
    birth = attempt("Date de naissance", lambda: parse_date(raw.get("birth_date")))
    d["birth_date"] = birth.isoformat() if birth else None
    for key, label, size in [("matricule", "Matricule", 20), ("birth_place", "Lieu de naissance", 120),
                             ("nationality", "Nationalité", 60), ("email", "E-mail", 254), ("phone", "Téléphone", 30),
                             ("address", "Adresse", 255), ("emergency_contact_name", "Contact d'urgence", 120),
                             ("emergency_contact_phone", "Tél. d'urgence", 30), ("cnss_number", "N° CNSS", 30),
                             ("ifu", "IFU", 20), ("department", "Département", 120), ("position", "Poste", 120)]:
        d[key] = attempt(label, lambda k=key, s=size: _text(raw.get(k), s)) or ""
    if d["email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", d["email"]):
        errors.append("E-mail invalide")
    d["nationality"] = d["nationality"] or "Béninoise"
    ms = norm(raw.get("marital_status"))
    d["marital_status"] = MARITAL.get(ms, "")
    if ms and not d["marital_status"]:
        errors.append(f"Situation matrimoniale inconnue « {raw.get('marital_status')} »")
    st = norm(raw.get("status"))
    d["status"] = STATUSES.get(st, "active")
    if st and st not in STATUSES:
        errors.append(f"Statut inconnu « {raw.get('status')} »")
    dep = raw.get("dependents")
    try:
        d["dependents"] = int(float(dep)) if dep not in (None, "") else 0
        if d["dependents"] < 0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Enfants à charge invalide")
        d["dependents"] = 0
    sal = raw.get("base_salary")
    d["base_salary"] = None
    if sal not in (None, ""):
        try:
            value = Decimal(str(sal).replace(" ", "").replace(" ", "").replace("\xa0", "").replace(",", "."))
            if value < 0:
                raise InvalidOperation
            d["base_salary"] = str(value.quantize(Decimal(1)))
        except InvalidOperation:
            errors.append("Salaire invalide")
    ct = norm(raw.get("contract_type"))
    d["contract_type"] = CONTRACTS.get(ct, "cdi")
    if ct and ct not in CONTRACTS:
        errors.append(f"Type de contrat inconnu « {raw.get('contract_type')} »")
    return d, errors


def analyse(company, rows, update_existing=False):
    """Classe chaque ligne : à créer, à mettre à jour, ignorée (doublon) ou en erreur."""
    existing_mat = {e.matricule.lower(): e for e in Employee.objects.filter(company=company).exclude(matricule="")}
    existing_mail = {e.email.lower(): e for e in Employee.objects.filter(company=company).exclude(email="")}
    seen_mat, seen_mail = set(), set()
    result = {"create": [], "update": [], "skip": [], "errors": []}
    for line, raw in rows:
        data, errors = clean_row(raw)
        mat, mail = data.get("matricule", "").lower(), data.get("email", "").lower()
        if mat and mat in seen_mat:
            errors.append("Matricule en double dans le fichier")
        if mail and mail in seen_mail:
            errors.append("E-mail en double dans le fichier")
        if errors:
            result["errors"].append({"line": line, "name": f"{data.get('last_name', '')} {data.get('first_name', '')}".strip(), "errors": errors})
            continue
        seen_mat.add(mat) if mat else None
        seen_mail.add(mail) if mail else None
        match = existing_mat.get(mat) if mat else None
        if match is None and mail:
            match = existing_mail.get(mail)
        item = {"line": line, "data": data}
        if match is None:
            result["create"].append(item)
        elif update_existing:
            item["employee_id"] = match.pk
            result["update"].append(item)
        else:
            item["reason"] = f"existe déjà ({match.matricule})"
            result["skip"].append(item)
    return result


@transaction.atomic
def apply(company, analysis):
    """Écrit en base. `analysis` provient d'`analyse` (éventuellement après passage par la session)."""
    depts, positions = {}, {}

    def dept(name):
        if not name:
            return None
        key = name.lower()
        if key not in depts:
            depts[key] = (Department.objects.filter(company=company, name__iexact=name).first()
                          or Department.objects.create(company=company, name=name))
        return depts[key]

    def position(name, department):
        if not name:
            return None
        key = name.lower()
        if key not in positions:
            positions[key] = (Position.objects.filter(company=company, title__iexact=name).first()
                              or Position.objects.create(company=company, title=name, department=department))
        return positions[key]

    fields = ["first_name", "last_name", "gender", "birth_place", "nationality", "marital_status", "dependents",
              "email", "phone", "address", "emergency_contact_name", "emergency_contact_phone", "cnss_number", "ifu", "status"]
    created = updated = 0
    new_ids = []
    for kind in ("create", "update"):
        for item in analysis[kind]:
            d = item["data"]
            department = dept(d["department"])
            pos = position(d["position"], department)
            values = {f: d[f] for f in fields}
            values["birth_date"] = datetime.date.fromisoformat(d["birth_date"]) if d["birth_date"] else None
            values["hire_date"] = datetime.date.fromisoformat(d["hire_date"])
            if kind == "create":
                emp = Employee(company=company, matricule=d["matricule"], department=department, position=pos, **values)
                emp.save()
                created += 1
                new_ids.append(emp.pk)
            else:
                emp = Employee.objects.get(pk=item["employee_id"], company=company)
                for k, v in values.items():
                    setattr(emp, k, v)
                if department:
                    emp.department = department
                if pos:
                    emp.position = pos
                emp.save()
                updated += 1
            if d["base_salary"] and kind == "create":
                Contract.objects.create(company=company, employee=emp, contract_type=d["contract_type"],
                                        start_date=values["hire_date"], base_salary=Decimal(d["base_salary"]))
    return created, updated, new_ids
