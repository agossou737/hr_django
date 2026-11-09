from django.contrib import admin

from .models import AttendanceRecord, FaceTemplate, ScanLog


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "check_in", "check_out", "late_minutes", "source_in", "company")
    list_filter = ("company", "date", "source_in")
    search_fields = ("employee__first_name", "employee__last_name", "employee__matricule")


@admin.register(FaceTemplate)
class FaceTemplateAdmin(admin.ModelAdmin):
    list_display = ("employee", "company", "consent_at", "created_at")
    list_filter = ("company",)
    exclude = ("descriptor",)  # donnée biométrique : jamais affichée


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "outcome", "employee", "distance", "company")
    list_filter = ("company", "outcome")
