import datetime
import hashlib
import secrets

from django.conf import settings
from django.utils import timezone
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from attendance.models import AttendanceRecord
from attendance.services import register_scan

from .models import FingerprintReader, ReaderUser, WebAuthnCredential

SESSION_REG = "webauthn_reg"
SESSION_AUTH = "webauthn_auth"


class BiometricError(ValueError):
    pass


# ------------------------------------------------------------------ WebAuthn
def rp_id(request):
    return getattr(settings, "WEBAUTHN_RP_ID", "") or request.get_host().split(":")[0]


def origin(request):
    return getattr(settings, "WEBAUTHN_ORIGIN", "") or f"{request.scheme}://{request.get_host()}"


def user_handle(employee):
    return f"{employee.company_id}:{employee.pk}".encode()


def registration_options(request, employee):
    opts = generate_registration_options(
        rp_id=rp_id(request), rp_name=settings.APP_NAME, user_id=user_handle(employee),
        user_name=employee.matricule or employee.full_name, user_display_name=employee.full_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED, user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
                             for c in employee.webauthn_credentials.all()],
    )
    request.session[SESSION_REG] = {"challenge": bytes_to_base64url(opts.challenge), "employee": employee.pk}
    return options_to_json(opts)


def finish_registration(request, employee, credential, label=""):
    state = request.session.pop(SESSION_REG, None)
    if not state or state["employee"] != employee.pk:
        raise BiometricError("Session d'enregistrement expirée, recommencez.")
    try:
        verified = verify_registration_response(
            credential=credential, expected_challenge=base64url_to_bytes(state["challenge"]),
            expected_rp_id=rp_id(request), expected_origin=origin(request), require_user_verification=True)
    except Exception as exc:
        raise BiometricError("Enregistrement refusé par la vérification de sécurité.") from exc
    cid = bytes_to_base64url(verified.credential_id)
    if WebAuthnCredential.objects.filter(credential_id=cid).exists():
        raise BiometricError("Cet appareil est déjà enregistré.")
    return WebAuthnCredential.objects.create(
        company=employee.company, employee=employee, credential_id=cid, public_key=verified.credential_public_key,
        sign_count=verified.sign_count, label=label[:80] or "Appareil")


def authentication_options(request):
    opts = generate_authentication_options(rp_id=rp_id(request), user_verification=UserVerificationRequirement.REQUIRED)
    request.session[SESSION_AUTH] = bytes_to_base64url(opts.challenge)
    return options_to_json(opts)


def authenticate(request, credential):
    """Vérifie l'assertion et renvoie la clé correspondante (limitée à l'entreprise de l'utilisateur)."""
    challenge = request.session.pop(SESSION_AUTH, None)
    if not challenge:
        raise BiometricError("Session expirée, recommencez.")
    raw_id = credential.get("rawId") or credential.get("id") if isinstance(credential, dict) else None
    if not raw_id:
        raise BiometricError("Réponse invalide.")
    cred = WebAuthnCredential.objects.select_related("employee__user", "company").filter(
        credential_id=raw_id, company=request.user.company).first()
    if cred is None:
        raise BiometricError("Appareil non reconnu.")
    try:
        verified = verify_authentication_response(
            credential=credential, expected_challenge=base64url_to_bytes(challenge), expected_rp_id=rp_id(request),
            expected_origin=origin(request), credential_public_key=bytes(cred.public_key),
            credential_current_sign_count=cred.sign_count, require_user_verification=True)
    except Exception as exc:
        raise BiometricError("Vérification biométrique refusée.") from exc
    cred.sign_count = verified.new_sign_count
    cred.last_used_at = timezone.now()
    cred.save(update_fields=["sign_count", "last_used_at"])
    return cred


def clock_with_credential(company, cred, device):
    return register_scan(company, cred.employee, None, device=device, source=AttendanceRecord.Source.FINGERPRINT)


# ------------------------------------------------------------ Lecteurs USB / API
def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


def create_reader(company, name):
    key = "rr_" + secrets.token_urlsafe(32)
    reader = FingerprintReader.objects.create(company=company, name=name, key_hash=_hash(key), key_prefix=key[:8])
    return reader, key


def reader_from_key(key):
    if not key:
        return None
    return FingerprintReader.objects.select_related("company").filter(key_hash=_hash(key), is_active=True).first()


def parse_timestamp(value, now=None):
    now = now or timezone.now()
    if not value:
        return now
    try:
        ts = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise BiometricError("Horodatage invalide (format ISO 8601 attendu).") from exc
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts)
    if ts > now + datetime.timedelta(minutes=2) or ts < now - datetime.timedelta(days=7):
        raise BiometricError("Horodatage hors de la plage acceptée (7 jours passés).")
    return ts


def scan_from_reader(reader, user_id, when=None):
    reader.last_seen_at = timezone.now()
    reader.save(update_fields=["last_seen_at"])
    link = ReaderUser.objects.select_related("employee").filter(company=reader.company, reader_user_id=str(user_id)).first()
    return register_scan(reader.company, link.employee if link else None, None, now=when,
                         source=AttendanceRecord.Source.FINGERPRINT)
