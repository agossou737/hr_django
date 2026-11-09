import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.generic import TemplateView

from accounts.mixins import HRRequiredMixin
from attendance.views import _recent_events
from employees.models import Employee

from . import services
from .models import FingerprintReader, ReaderUser, WebAuthnCredential


def _json(request):
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _bad(message, status=400):
    return JsonResponse({"status": "error", "message": message}, status=status)


class CompanyMemberMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.company_id is None:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def _target_employee(request, pk=None):
    """Employé concerné par l'enregistrement : soi-même, ou n'importe qui pour les RH."""
    if pk is None:
        emp = Employee.objects.filter(company=request.user.company, user=request.user).first()
        if emp is None:
            raise PermissionDenied
        return emp
    emp = get_object_or_404(Employee, pk=pk, company=request.user.company)
    if not (request.user.can_manage_hr or emp.user_id == request.user.pk):
        raise PermissionDenied
    return emp


def can_clock(user):
    if not user.is_authenticated or user.company_id is None:
        return False
    if user.role in ("kiosk", "hr", "admin"):
        return True
    return user.company.fingerprint_self_service


# ---------------------------------------------------- Appareils d'un employé
@method_decorator(ensure_csrf_cookie, name="dispatch")
class CredentialsView(CompanyMemberMixin, TemplateView):
    template_name = "biometrics/credentials.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emp = _target_employee(self.request, self.kwargs.get("pk"))
        base = f"/biometrie/employes/{emp.pk}"
        ctx.update(emp=emp, credentials=emp.webauthn_credentials.all(), own=emp.user_id == self.request.user.pk,
                   options_url=f"{base}/options/", verify_url=f"{base}/verifier/")
        return ctx


class RegisterOptionsView(CompanyMemberMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        emp = _target_employee(request, pk)
        return HttpResponse(services.registration_options(request, emp), content_type="application/json")


class RegisterVerifyView(CompanyMemberMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        emp = _target_employee(request, pk)
        payload = _json(request)
        if payload is None or not isinstance(payload.get("credential"), dict):
            return _bad("Requête invalide.")
        try:
            services.finish_registration(request, emp, payload["credential"], str(payload.get("label", "")))
        except services.BiometricError as exc:
            return _bad(str(exc))
        return JsonResponse({"status": "ok", "message": "Appareil enregistré."})


class CredentialDeleteView(CompanyMemberMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        cred = get_object_or_404(WebAuthnCredential.objects.select_related("employee"), pk=pk, company=request.user.company)
        if not (request.user.can_manage_hr or cred.employee.user_id == request.user.pk):
            raise PermissionDenied
        cred.delete()
        messages.success(request, "Appareil supprimé.")
        return redirect(request.POST.get("next") or "biometrics:mine")


# ---------------------------------------------------------------- Pointage
@method_decorator([never_cache, ensure_csrf_cookie], name="dispatch")
class ClockView(CompanyMemberMixin, TemplateView):
    template_name = "biometrics/clock.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["allowed"] = can_clock(self.request.user)
        ctx["is_staff_kiosk"] = self.request.user.role != "employee"
        return ctx


class ClockOptionsView(CompanyMemberMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        if not can_clock(request.user):
            raise PermissionDenied
        return HttpResponse(services.authentication_options(request), content_type="application/json")


class ClockVerifyView(CompanyMemberMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        if not can_clock(request.user):
            raise PermissionDenied
        payload = _json(request)
        if payload is None or not isinstance(payload.get("credential"), dict):
            return _bad("Requête invalide.")
        try:
            cred = services.authenticate(request, payload["credential"])
            if request.user.role == "employee" and cred.employee.user_id != request.user.pk:
                raise services.BiometricError("Cet appareil n'est pas le vôtre.")
        except services.BiometricError as exc:
            return _bad(str(exc), 403)
        result = services.clock_with_credential(request.user.company, cred, request.user)
        body = {"status": result.outcome, "success": result.success, "message": result.message,
                "employee": {"name": cred.employee.full_name, "matricule": cred.employee.matricule}}
        if result.record:
            local = timezone.localtime(result.record.check_out or result.record.check_in)
            body.update(time=local.strftime("%H:%M:%S"), date=local.strftime("%d/%m/%Y"),
                        late_minutes=result.record.late_minutes)
        if request.user.role != "employee":
            body["recent"] = _recent_events(request.user.company)
        return JsonResponse(body)


# ---------------------------------------------------------- Administration RH
class ManageView(HRRequiredMixin, TemplateView):
    template_name = "biometrics/manage.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.request.user.company
        ctx.update(
            readers=FingerprintReader.objects.filter(company=c),
            mappings=ReaderUser.objects.filter(company=c).select_related("employee"),
            credentials=WebAuthnCredential.objects.filter(company=c).select_related("employee"),
            employees=Employee.objects.filter(company=c).exclude(status="left"),
            api_url=self.request.build_absolute_uri("/biometrie/api/lecteur/"),
        )
        return ctx


class ReaderCreateView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        name = request.POST.get("name", "").strip()[:100]
        if not name:
            messages.error(request, "Donnez un nom au lecteur.")
            return redirect("biometrics:manage")
        reader, key = services.create_reader(request.user.company, name)
        return render(request, "biometrics/reader_created.html", {"reader": reader, "key": key,
                      "api_url": request.build_absolute_uri("/biometrie/api/lecteur/")})


class ReaderToggleView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        r = get_object_or_404(FingerprintReader, pk=pk, company=request.user.company)
        r.is_active = not r.is_active
        r.save(update_fields=["is_active"])
        return redirect("biometrics:manage")


class ReaderDeleteView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        get_object_or_404(FingerprintReader, pk=pk, company=request.user.company).delete()
        return redirect("biometrics:manage")


class MappingAddView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        company = request.user.company
        emp = Employee.objects.filter(company=company, pk=request.POST.get("employee") or 0).first()
        uid = request.POST.get("reader_user_id", "").strip()[:40]
        if not emp or not uid:
            messages.error(request, "Employé et identifiant requis.")
        elif ReaderUser.objects.filter(company=company, reader_user_id=uid).exists():
            messages.error(request, "Cet identifiant de lecteur est déjà attribué.")
        else:
            ReaderUser.objects.create(company=company, employee=emp, reader_user_id=uid)
            messages.success(request, "Correspondance enregistrée.")
        return redirect("biometrics:manage")


class MappingDeleteView(HRRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        get_object_or_404(ReaderUser, pk=pk, company=request.user.company).delete()
        return redirect("biometrics:manage")


# ------------------------------------------------------------ API des lecteurs
@method_decorator(csrf_exempt, name="dispatch")
class ReaderScanAPIView(View):
    """POST JSON {"user_id": "12", "timestamp": "2026-03-02T07:58:00+01:00" (facultatif)}
    avec l'en-tête « Authorization: Bearer <clé du lecteur> »."""

    http_method_names = ["post"]

    def post(self, request):
        auth = request.headers.get("Authorization", "")
        reader = services.reader_from_key(auth[7:].strip() if auth.lower().startswith("bearer ") else "")
        if reader is None:
            return _bad("Clé de lecteur invalide ou désactivée.", 401)
        payload = _json(request)
        if payload is None or payload.get("user_id") in (None, ""):
            return _bad("Champ « user_id » requis.")
        try:
            when = services.parse_timestamp(payload.get("timestamp"))
        except services.BiometricError as exc:
            return _bad(str(exc))
        result = services.scan_from_reader(reader, payload["user_id"], when)
        body = {"status": result.outcome, "success": result.success, "message": result.message}
        if result.employee:
            body["employee"] = {"name": result.employee.full_name, "matricule": result.employee.matricule}
        return JsonResponse(body, status=404 if result.outcome == "unknown" else 200)
