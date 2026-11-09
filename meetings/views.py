from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView, View

from accounts.mixins import HRRequiredMixin
from leaves.views import CompanyUserMixin

from . import services
from .forms import ActionForm, MeetingForm, MinutesForm
from .models import Meeting, MeetingAction


class OrganizerMixin(CompanyUserMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not services.can_organize(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class MyMeetingsView(CompanyUserMixin, ListView):
    template_name = "meetings/mine.html"
    context_object_name = "meetings"

    def get_queryset(self):
        return services.visible_meetings(self.request.user).prefetch_related("participants")


class MeetingListView(HRRequiredMixin, ListView):
    template_name = "meetings/list.html"
    context_object_name = "meetings"
    paginate_by = 25

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") in ("csv", "xlsx", "pdf"):
            from companies.exports import export_table

            rows = [[m.reference, m.date, m.start_time.strftime("%H:%M"), m.title, m.location,
                     m.organizer.get_full_name() if m.organizer else "", m.participants.count(), m.get_status_display()]
                    for m in self.get_queryset()]
            return export_table(request.GET["export"], "reunions", "Réunions",
                                ["Réf.", "Date", "Heure", "Titre", "Lieu", "Organisateur", "Participants", "Statut"], rows,
                                request.user.company)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return Meeting.objects.filter(company=self.request.user.company).select_related("organizer")


class MeetingCreateView(OrganizerMixin, CreateView):
    model = Meeting
    form_class = MeetingForm
    template_name = "form_page.html"
    extra_context = {"title": "Planifier une réunion", "cancel_url": reverse_lazy("meetings:mine")}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def form_valid(self, form):
        form.instance.company, form.instance.organizer = self.request.user.company, self.request.user
        response = super().form_valid(form)
        services.notify_invitation(self.object)
        messages.success(self.request, "Réunion planifiée, les participants sont convoqués.")
        return response

    def get_success_url(self):
        return self.object.get_absolute_url() if hasattr(self.object, "get_absolute_url") else \
            reverse_lazy("meetings:detail", args=[self.object.pk])


class _MeetingMixin(CompanyUserMixin):
    def get_meeting(self, pk, edit=False):
        m = get_object_or_404(Meeting.objects.select_related("organizer", "company"), pk=pk, company=self.request.user.company)
        if not (services.can_edit(self.request.user, m) if edit else services.can_view(self.request.user, m)):
            raise PermissionDenied
        return m


class MeetingUpdateView(_MeetingMixin, UpdateView):
    form_class = MeetingForm
    template_name = "form_page.html"

    def get_object(self, queryset=None):
        m = self.get_meeting(self.kwargs["pk"], edit=True)
        if m.status != Meeting.Status.PLANNED:
            raise PermissionDenied
        return m

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["company"] = self.request.user.company
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title="Modifier la réunion", cancel_url=reverse_lazy("meetings:detail", args=[self.object.pk]))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        services.notify_invitation(self.object, update=True)
        messages.success(self.request, "Réunion modifiée, les participants sont prévenus.")
        return response

    def get_success_url(self):
        return reverse_lazy("meetings:detail", args=[self.object.pk])


class MeetingDetailView(_MeetingMixin, TemplateView):
    template_name = "meetings/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        m = self.get_meeting(self.kwargs["pk"])
        editable = services.can_edit(self.request.user, m)
        ctx.update(meeting=m, editable=editable, participants=m.participants.all(),
                   actions=m.actions.select_related("owner"),
                   action_form=ActionForm(meeting=m) if editable and m.status != m.Status.CANCELLED else None,
                   me=getattr(self.request.user, "employee", None))
        return ctx


class MinutesView(_MeetingMixin, UpdateView):
    form_class = MinutesForm
    template_name = "form_page.html"

    def get_object(self, queryset=None):
        m = self.get_meeting(self.kwargs["pk"], edit=True)
        if m.status == Meeting.Status.CANCELLED:
            raise PermissionDenied
        return m

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(title=f"Compte rendu : {self.object.title}",
                   cancel_url=reverse_lazy("meetings:detail", args=[self.object.pk]))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        services.publish_minutes(self.object)
        messages.success(self.request, "Compte rendu publié, les participants sont notifiés.")
        return response

    def get_success_url(self):
        return reverse_lazy("meetings:detail", args=[self.object.pk])


class CancelView(_MeetingMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        m = self.get_meeting(pk, edit=True)
        if m.status == Meeting.Status.PLANNED:
            services.cancel(m)
            messages.success(request, "Réunion annulée.")
        return redirect("meetings:detail", pk=pk)


class ActionAddView(_MeetingMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        m = self.get_meeting(pk, edit=True)
        form = ActionForm(request.POST, meeting=m)
        if m.status != Meeting.Status.CANCELLED and form.is_valid():
            a = form.save(commit=False)
            a.company, a.meeting = m.company, m
            a.save()
            if a.owner and a.owner.user_id:
                from notifications.services import notify

                notify([a.owner.user], f"Action issue de la réunion « {m.title} »", a.description,
                       reverse_lazy("meetings:detail", args=[m.pk]))
        else:
            messages.error(request, "Action invalide.")
        return redirect("meetings:detail", pk=pk)


class ActionToggleView(CompanyUserMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        a = get_object_or_404(MeetingAction.objects.select_related("meeting", "owner"), pk=pk, company=request.user.company)
        owner_ok = a.owner and a.owner.user_id == request.user.pk
        if not (owner_ok or services.can_edit(request.user, a.meeting)):
            raise PermissionDenied
        a.done = not a.done
        a.save(update_fields=["done"])
        return redirect("meetings:detail", pk=a.meeting_id)


class PdfView(_MeetingMixin, View):
    def get(self, request, pk, which):
        m = self.get_meeting(pk)
        if which == "convocation":
            data = services.convocation_pdf(m)
        elif which == "compte-rendu" and m.minutes:
            data = services.minutes_pdf(m)
        else:
            raise PermissionDenied
        resp = HttpResponse(data, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{m.reference}-{which}.pdf"'
        return resp
