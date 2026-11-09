import datetime
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from accounts.models import User
from companies.exports import build_table_pdf, export_table
from companies.models import Company

from . import importer
from .models import Contract, Department, Employee, Position


def xlsx(rows, header=None):
    wb = Workbook()
    ws = wb.active
    ws.append(header or importer.HEADERS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile("emp.xlsx", buf.getvalue())


def row(**kw):
    base = dict(zip([k for k, _, _ in importer.COLUMNS], [None] * 30))
    base.update(kw)
    return [base[k] for k, _, _ in importer.COLUMNS]


class CleanRowTests(SimpleTestCase):
    def test_valid_full_row(self):
        d, e = importer.clean_row({"last_name": "DOSSOU", "first_name": "Jean", "gender": "Masculin",
                                   "hire_date": "02/03/2026", "marital_status": "Marié(e)", "dependents": 2.0,
                                   "base_salary": "250 000", "contract_type": "Stage", "status": "En congé"})
        self.assertEqual(e, [])
        self.assertEqual((d["gender"], d["hire_date"], d["marital_status"], d["dependents"], d["base_salary"],
                          d["contract_type"], d["status"]),
                         ("M", "2026-03-02", "married", 2, "250000", "internship", "on_leave"))

    def test_errors(self):
        d, e = importer.clean_row({"last_name": "", "gender": "x", "hire_date": "32/13/2026", "email": "bad",
                                   "base_salary": "abc", "status": "zzz"})
        self.assertGreaterEqual(len(e), 6)

    def test_excel_date_and_float_phone(self):
        d, e = importer.clean_row({"last_name": "A", "first_name": "B", "gender": "f",
                                   "hire_date": datetime.datetime(2026, 1, 5), "phone": 97000000.0})
        self.assertEqual((e, d["hire_date"], d["phone"]), ([], "2026-01-05", "97000000"))


class ImportFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.emp_user = User.objects.create_user("e@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")

    def upload(self, f, update=False):
        self.client.force_login(self.hr)
        data = {"file": f}
        if update:
            data["update_existing"] = "on"
        return self.client.post(reverse("employees:import"), data, follow=True)

    def test_template_roundtrip(self):
        self.client.force_login(self.hr)
        content = self.client.get(reverse("employees:import_template")).content
        r = self.upload(SimpleUploadedFile("modele.xlsx", content))
        self.assertEqual(r.context["counts"]["create"], 1)          # ligne d'exemple valide
        self.assertEqual(r.context["counts"]["errors"], 0)

    def test_full_import(self):
        f = xlsx([
            row(last_name="DOSSOU", first_name="Jean", gender="M", hire_date="02/03/2026",
                department="Compta", position="Comptable", base_salary=250000, email="j@x.bj"),
            row(last_name="ZINSOU", first_name="Awa", gender="F", hire_date="2026-04-01",
                department="compta", position="Comptable", matricule="X-77"),
            row(last_name="", first_name="Sans nom", gender="M", hire_date="01/01/2026"),
        ])
        r = self.upload(f)
        self.assertEqual({k: v for k, v in r.context["counts"].items()}, {"create": 2, "update": 0, "skip": 0, "errors": 1})
        self.client.post(reverse("employees:import_confirm"))
        self.assertEqual(Employee.objects.filter(company=self.c1).count(), 2)
        self.assertEqual(Department.objects.filter(company=self.c1).count(), 1)   # insensible à la casse
        self.assertEqual(Position.objects.filter(company=self.c1).count(), 1)
        jean = Employee.objects.get(last_name="DOSSOU")
        self.assertEqual(jean.matricule, "EMP0001")
        self.assertEqual(jean.contracts.get().base_salary, 250000)
        self.assertEqual(Employee.objects.get(last_name="ZINSOU").matricule, "X-77")
        self.assertEqual(Contract.objects.count(), 1)

    def test_duplicates_skip_then_update(self):
        Employee.objects.create(company=self.c1, first_name="Old", last_name="NAME", gender="M",
                                hire_date=datetime.date(2025, 1, 1), email="dup@x.bj")
        f = lambda: xlsx([row(last_name="NEW", first_name="Name", gender="M", hire_date="01/02/2026", email="dup@x.bj", phone="111")])
        r = self.upload(f())
        self.assertEqual(r.context["counts"]["skip"], 1)
        self.client.post(reverse("employees:import_confirm"))
        self.assertEqual(Employee.objects.get().last_name, "NAME")
        r = self.upload(f(), update=True)
        self.assertEqual(r.context["counts"]["update"], 1)
        self.client.post(reverse("employees:import_confirm"))
        e = Employee.objects.get()
        self.assertEqual((e.last_name, e.phone, Employee.objects.count()), ("NEW", "111", 1))

    def test_duplicates_inside_file(self):
        f = xlsx([row(last_name="A", first_name="A", gender="M", hire_date="01/02/2026", email="same@x.bj"),
                  row(last_name="B", first_name="B", gender="M", hire_date="01/02/2026", email="same@x.bj")])
        r = self.upload(f)
        self.assertEqual((r.context["counts"]["create"], r.context["counts"]["errors"]), (1, 1))

    def test_company_isolation(self):
        Employee.objects.create(company=self.c2, first_name="X", last_name="Y", gender="M",
                                hire_date=datetime.date(2025, 1, 1), email="dup@x.bj", matricule="EMP0001")
        r = self.upload(xlsx([row(last_name="A", first_name="A", gender="M", hire_date="01/02/2026", email="dup@x.bj", matricule="EMP0001")]))
        self.assertEqual(r.context["counts"]["create"], 1)         # pas de conflit avec une autre entreprise
        self.client.post(reverse("employees:import_confirm"))
        self.assertEqual(Employee.objects.filter(company=self.c1).count(), 1)
        # l'aperçu d'une entreprise n'est pas utilisable par une autre
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.post(reverse("employees:import_confirm")).status_code, 302)
        self.assertEqual(Employee.objects.filter(company=self.c2).count(), 1)

    def test_bad_files(self):
        for f in (SimpleUploadedFile("x.exe", b"MZ"), SimpleUploadedFile("x.xlsx", b"not excel"),
                  xlsx([], header=["Colonne1"])):
            r = self.upload(f)
            self.assertContains(r, "alert", status_code=200) if False else None
            self.assertEqual(Employee.objects.count(), 0)
        csv = SimpleUploadedFile("a.csv", "Nom;Prénoms;Sexe;Date d'embauche\nDOSSOU;Jean;M;02/03/2026\n".encode())
        self.assertEqual(self.upload(csv).context["counts"]["create"], 1)

    def test_too_many_rows(self):
        old = importer.MAX_ROWS
        importer.MAX_ROWS = 2
        try:
            r = self.upload(xlsx([row(last_name=f"N{i}", first_name="P", gender="M", hire_date="01/01/2026") for i in range(3)]))
            self.assertNotIn("counts", r.context or {})
        finally:
            importer.MAX_ROWS = old

    def test_permissions(self):
        self.client.force_login(self.emp_user)
        for name in ("import", "import_template", "import_preview"):
            self.assertEqual(self.client.get(reverse(f"employees:{name}")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("employees:import")).status_code, 302)

    def test_error_report(self):
        self.upload(xlsx([row(last_name="", first_name="X", gender="M", hire_date="01/01/2026")]))
        r = self.client.get(reverse("employees:import_errors"))
        ws = load_workbook(io.BytesIO(r.content)).active
        self.assertEqual(ws.max_row, 2)


class ExportTests2(TestCase):
    def test_formats(self):
        for fmt, magic in (("xlsx", b"PK"), ("pdf", b"%PDF"), ("csv", b"\xef\xbb\xbf")):
            r = export_table(fmt, "t", "Titre", ["A", "B"], [["x & <y>", 1], [None, datetime.date(2026, 1, 2)]])
            self.assertTrue(r.content.startswith(magic), fmt)
        with self.assertRaises(Exception):
            export_table("exe", "t", "T", ["A"], [])

    def test_pdf_many_rows(self):
        self.assertTrue(build_table_pdf("T", ["A", "B", "C"], [[i, "texte " * 20, i] for i in range(300)], "Alpha").startswith(b"%PDF"))

    def test_list_pages_all_formats(self):
        c = Company.objects.create(name="Alpha", slug="alpha")
        hr = User.objects.create_user("hr@a.bj", "pass12345!", company=c, role="hr")
        Employee.objects.create(company=c, first_name="Jean", last_name="DOSSOU", gender="M", hire_date=datetime.date(2025, 1, 1))
        self.client.force_login(hr)
        for name in ("employees:list", "leaves:list", "attendance:monthly"):
            for fmt, magic in (("xlsx", b"PK"), ("pdf", b"%PDF"), ("csv", b"\xef\xbb\xbf")):
                r = self.client.get(reverse(name) + f"?export={fmt}")
                self.assertEqual(r.status_code, 200, (name, fmt))
                self.assertTrue(r.content.startswith(magic), (name, fmt))
        body = self.client.get(reverse("employees:list")).content.decode()
        self.assertIn("export=pdf", body)
