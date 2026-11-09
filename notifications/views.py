from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import ListView, View

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/list.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationOpenView(LoginRequiredMixin, View):
    """Marque comme lue puis redirige vers le lien de la notification."""

    def get(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, user=request.user)
        if not n.is_read:
            n.is_read = True
            n.save(update_fields=["is_read"])
        target = n.url
        if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}) and target.startswith("/"):
            return redirect(target)
        return redirect("notifications:list")


class MarkAllReadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect("notifications:list")
