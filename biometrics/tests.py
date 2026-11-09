import datetime
import hashlib
import json
import struct
from types import SimpleNamespace
from unittest import mock

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, encode_cbor

from accounts.models import User
from attendance.models import AttendanceRecord, ScanLog
from companies.models import Company
from employees.models import Employee

from . import services
from .models import FingerprintReader, ReaderUser, WebAuthnCredential


def emp(company, first, last, **kw):
    return Employee.objects.create(company=company, first_name=first, last_name=last, gender="M",
                                   hire_date=datetime.date(2024, 1, 1), **kw)


class SoftAuthenticator:
    """Authentificateur logiciel : produit de vraies signatures ECDSA pour tester la vérification WebAuthn."""

    def __init__(self, rp_id="testserver", origin="http://testserver"):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = b"cred-" + bytes_to_base64url(hashlib.sha256(str(id(self)).encode()).digest()).encode()[:12]
        self.rp_id, self.origin, self.counter = rp_id, origin, 0

    @property
    def public_key_cose(self):
        n = self.key.public_key().public_numbers()
        return encode_cbor({1: 2, 3: -7, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")})

    def assertion(self, challenge_b64, uv=True, counter=None):
        self.counter = counter if counter is not None else self.counter + 1
        flags = 0x01 | (0x04 if uv else 0)
        auth_data = hashlib.sha256(self.rp_id.encode()).digest() + bytes([flags]) + struct.pack(">I", self.counter)
        client = json.dumps({"type": "webauthn.get", "challenge": challenge_b64, "origin": self.origin}).encode()
        sig = self.key.sign(auth_data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        cid = bytes_to_base64url(self.cred_id)
        return {"id": cid, "rawId": cid, "type": "public-key", "response": {
            "clientDataJSON": bytes_to_base64url(client), "authenticatorData": bytes_to_base64url(auth_data),
            "signature": bytes_to_base64url(sig), "userHandle": None}, "clientExtensionResults": {}}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c1 = Company.objects.create(name="Alpha", slug="alpha")
        cls.c2 = Company.objects.create(name="Beta", slug="beta")
        cls.hr = User.objects.create_user("hr@a.bj", "pass12345!", company=cls.c1, role="hr")
        cls.kiosk = User.objects.create_user("k@a.bj", "pass12345!", company=cls.c1, role="kiosk")
        cls.u1 = User.objects.create_user("e1@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.u2 = User.objects.create_user("e2@a.bj", "pass12345!", company=cls.c1, role="employee")
        cls.hr_b = User.objects.create_user("hr@b.bj", "pass12345!", company=cls.c2, role="hr")
        cls.e1 = emp(cls.c1, "Jean", "DOSSOU", user=cls.u1)
        cls.e2 = emp(cls.c1, "Awa", "ZINSOU", user=cls.u2)
        cls.eb = emp(cls.c2, "Paul", "KPADE")

    def enroll(self, employee=None, device=None):
        device = device or SoftAuthenticator()
        WebAuthnCredential.objects.create(company=self.c1, employee=employee or self.e1,
                                          credential_id=bytes_to_base64url(device.cred_id),
                                          public_key=device.public_key_cose, label="Test")
        return device

    def challenge(self):
        r = self.client.post(reverse("biometrics:clock_options"), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        return r.json()["challenge"]

    def clock(self, device, **kw):
        return self.client.post(reverse("biometrics:clock_verify"),
                                json.dumps({"credential": device.assertion(self.challenge(), **kw)}),
                                content_type="application/json")


class WebAuthnClockTests(Base):
    def test_kiosk_clock_in_then_replay_and_counter(self):
        dev = self.enroll()
        self.client.force_login(self.kiosk)
        r = self.clock(dev)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"], body)
        self.assertEqual(body["employee"]["name"], "Jean DOSSOU")
        rec = AttendanceRecord.objects.get()
        self.assertEqual(rec.source_in, "fingerprint")
        self.assertEqual(ScanLog.objects.filter(outcome="in").count(), 1)
        cred = WebAuthnCredential.objects.get()
        self.assertEqual(cred.sign_count, 1)
        self.assertIsNotNone(cred.last_used_at)
        # même challenge rejoué : refusé (le défi est à usage unique)
        r = self.client.post(reverse("biometrics:clock_verify"),
                             json.dumps({"credential": dev.assertion("AAAA", counter=2)}), content_type="application/json")
        self.assertEqual(r.status_code, 403)
        # compteur qui régresse (clone d'appareil) : refusé
        r = self.clock(dev, counter=1)
        self.assertEqual(r.status_code, 403)

    def test_signature_forgery_and_missing_uv_rejected(self):
        dev = self.enroll()
        attacker = SoftAuthenticator()
        attacker.cred_id = dev.cred_id  # même identifiant, autre clé privée
        self.client.force_login(self.kiosk)
        self.assertEqual(self.clock(attacker).status_code, 403)
        self.assertEqual(self.clock(dev, uv=False).status_code, 403)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_wrong_origin_rejected(self):
        dev = self.enroll()
        dev.origin = "https://evil.example"
        self.client.force_login(self.kiosk)
        self.assertEqual(self.clock(dev).status_code, 403)

    def test_company_isolation(self):
        dev = self.enroll()
        self.client.force_login(self.hr_b)
        r = self.clock(dev)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["message"], "Appareil non reconnu.")

    def test_employee_self_service_flag_and_ownership(self):
        dev1, dev2 = self.enroll(self.e1), self.enroll(self.e2)
        self.client.force_login(self.u1)
        self.assertEqual(self.client.post(reverse("biometrics:clock_options")).status_code, 403)  # désactivé
        self.assertContains(self.client.get(reverse("biometrics:clock")), "n'est pas activé")
        self.c1.fingerprint_self_service = True
        self.c1.save()
        self.client.force_login(self.u1)
        r = self.clock(dev2)  # l'appareil d'un collègue
        self.assertEqual(r.status_code, 403)
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertTrue(self.clock(dev1).json()["success"])
        self.assertNotIn("recent", self.clock(dev1).json())

    def test_second_scan_is_duplicate_then_inactive(self):
        dev = self.enroll()
        self.client.force_login(self.kiosk)
        self.clock(dev)
        self.assertEqual(self.clock(dev).json()["status"], "duplicate")
        AttendanceRecord.objects.all().delete()
        self.e1.status = "suspended"
        self.e1.save()
        self.assertEqual(self.clock(dev).json()["status"], "inactive")

    def test_late_fingerprint_clock_creates_explanation(self):
        from explanations.models import Explanation

        dev = self.enroll()
        self.client.force_login(self.kiosk)
        late = timezone.make_aware(datetime.datetime.combine(timezone.localdate(), datetime.time(11, 0)))
        with mock.patch("attendance.services.timezone.now", return_value=late):
            self.assertTrue(self.clock(dev).json()["success"])
        self.assertEqual(Explanation.objects.count(), 1)


class RegistrationTests(Base):
    def fake_verified(self, device):
        return SimpleNamespace(credential_id=device.cred_id, credential_public_key=device.public_key_cose, sign_count=0)

    def test_register_flow_self_and_hr_not_others(self):
        dev = SoftAuthenticator()
        self.client.force_login(self.u1)
        r = self.client.post(reverse("biometrics:register_options", args=[self.e1.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("challenge", r.json())
        payload = json.dumps({"credential": {"id": "x"}, "label": "Mon téléphone"})
        with mock.patch("biometrics.services.verify_registration_response", return_value=self.fake_verified(dev)):
            r = self.client.post(reverse("biometrics:register_verify", args=[self.e1.pk]), payload,
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        cred = WebAuthnCredential.objects.get()
        self.assertEqual((cred.employee, cred.label), (self.e1, "Mon téléphone"))
        # défi usage unique : un second verify sans options est refusé
        with mock.patch("biometrics.services.verify_registration_response", return_value=self.fake_verified(SoftAuthenticator())):
            r = self.client.post(reverse("biometrics:register_verify", args=[self.e1.pk]), payload,
                                 content_type="application/json")
        self.assertEqual(r.status_code, 400)
        # un collègue ne peut pas enregistrer pour autrui ; un autre tenant non plus
        self.client.force_login(self.u2)
        self.assertEqual(self.client.post(reverse("biometrics:register_options", args=[self.e1.pk])).status_code, 403)
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.post(reverse("biometrics:register_options", args=[self.e1.pk])).status_code, 404)
        self.client.force_login(self.hr)
        self.assertEqual(self.client.post(reverse("biometrics:register_options", args=[self.e1.pk])).status_code, 200)

    def test_failed_verification_and_duplicate_device(self):
        self.client.force_login(self.u1)
        self.client.post(reverse("biometrics:register_options", args=[self.e1.pk]))
        r = self.client.post(reverse("biometrics:register_verify", args=[self.e1.pk]),
                             json.dumps({"credential": {"id": "x"}}), content_type="application/json")
        self.assertEqual(r.status_code, 400)  # vraie vérification, données invalides
        self.assertFalse(WebAuthnCredential.objects.exists())
        dev = self.enroll()
        self.client.post(reverse("biometrics:register_options", args=[self.e2.pk]))
        self.client.force_login(self.u2)
        self.client.post(reverse("biometrics:register_options", args=[self.e2.pk]))
        with mock.patch("biometrics.services.verify_registration_response", return_value=self.fake_verified(dev)):
            r = self.client.post(reverse("biometrics:register_verify", args=[self.e2.pk]),
                                 json.dumps({"credential": {"id": "x"}}), content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_pages_and_delete(self):
        self.enroll()
        self.client.force_login(self.u1)
        self.assertContains(self.client.get(reverse("biometrics:mine")), "Appareils biométriques")
        self.assertEqual(self.client.get(reverse("biometrics:employee", args=[self.e2.pk])).status_code, 403)
        cred = WebAuthnCredential.objects.get()
        self.client.force_login(self.u2)
        self.assertEqual(self.client.post(reverse("biometrics:credential_delete", args=[cred.pk])).status_code, 403)
        self.client.force_login(self.u1)
        self.client.post(reverse("biometrics:credential_delete", args=[cred.pk]))
        self.assertFalse(WebAuthnCredential.objects.exists())


class ReaderAPITests(Base):
    def setUp(self):
        self.reader, self.key = services.create_reader(self.c1, "Entrée")
        ReaderUser.objects.create(company=self.c1, employee=self.e1, reader_user_id="12")
        self.url = reverse("biometrics:api_reader")

    def post(self, data, key=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {key or self.key}"}
        return self.client.post(self.url, json.dumps(data), content_type="application/json", **headers)

    def test_scan_check_in_and_out(self):
        r = self.post({"user_id": "12"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        rec = AttendanceRecord.objects.get()
        self.assertEqual(rec.source_in, "fingerprint")
        self.reader.refresh_from_db()
        self.assertIsNotNone(self.reader.last_seen_at)
        self.assertEqual(self.post({"user_id": 12}).json()["status"], "duplicate")

    def test_auth_required_and_inactive_key(self):
        self.assertEqual(self.client.post(self.url, "{}", content_type="application/json").status_code, 401)
        self.assertEqual(self.post({"user_id": "12"}, key="rr_faux").status_code, 401)
        self.reader.is_active = False
        self.reader.save()
        self.assertEqual(self.post({"user_id": "12"}).status_code, 401)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_key_is_hashed_and_not_cross_tenant(self):
        self.assertNotIn(self.key, self.reader.key_hash)
        self.assertEqual(len(self.reader.key_hash), 64)
        ReaderUser.objects.create(company=self.c2, employee=self.eb, reader_user_id="99")
        r = self.post({"user_id": "99"})  # identifiant d'une autre entreprise
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["status"], "unknown")
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_unknown_user_and_bad_payload(self):
        self.assertEqual(self.post({"user_id": "777"}).status_code, 404)
        self.assertEqual(self.post({}).status_code, 400)
        r = self.client.post(self.url, "pas du json", content_type="application/json",
                             HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(r.status_code, 400)

    def test_timestamps(self):
        now = timezone.now()
        past = (now - datetime.timedelta(hours=3)).isoformat()
        self.assertEqual(self.post({"user_id": "12", "timestamp": past}).status_code, 200)
        self.assertEqual(AttendanceRecord.objects.get().check_in.replace(microsecond=0),
                         datetime.datetime.fromisoformat(past).replace(microsecond=0))
        self.assertEqual(self.post({"user_id": "12", "timestamp": "n'importe quoi"}).status_code, 400)
        self.assertEqual(self.post({"user_id": "12", "timestamp": (now + datetime.timedelta(hours=1)).isoformat()}).status_code, 400)
        self.assertEqual(self.post({"user_id": "12", "timestamp": (now - datetime.timedelta(days=30)).isoformat()}).status_code, 400)


class ManageTests(Base):
    def test_hr_manages_readers_and_mappings(self):
        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("biometrics:manage")).status_code, 200)
        r = self.client.post(reverse("biometrics:reader_create"), {"name": "Porte"})
        self.assertContains(r, "rr_")
        reader = FingerprintReader.objects.get()
        self.client.post(reverse("biometrics:mapping_add"), {"employee": self.e1.pk, "reader_user_id": "5"})
        self.client.post(reverse("biometrics:mapping_add"), {"employee": self.e2.pk, "reader_user_id": "5"})
        self.client.post(reverse("biometrics:mapping_add"), {"employee": self.eb.pk, "reader_user_id": "6"})
        self.assertEqual(ReaderUser.objects.count(), 1)
        self.client.post(reverse("biometrics:reader_toggle", args=[reader.pk]))
        reader.refresh_from_db()
        self.assertFalse(reader.is_active)
        self.client.force_login(self.u1)
        for name in ("manage",):
            self.assertEqual(self.client.get(reverse(f"biometrics:{name}")).status_code, 403)
        self.assertEqual(self.client.post(reverse("biometrics:reader_delete", args=[reader.pk])).status_code, 403)
        self.client.force_login(self.hr_b)
        self.assertEqual(self.client.post(reverse("biometrics:reader_delete", args=[reader.pk])).status_code, 404)
        self.client.force_login(self.hr)
        self.client.post(reverse("biometrics:reader_delete", args=[reader.pk]))
        self.assertFalse(FingerprintReader.objects.exists())
