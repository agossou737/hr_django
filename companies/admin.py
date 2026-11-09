from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "phone", "email", "is_active")
    fieldsets = (
        (None, {"fields": ("name", "slug", "is_active", "logo")}),
        ("Identité légale", {"fields": ("ifu", "rccm", "cnss_number")}),
        ("Contact", {"fields": ("address", "city", "phone", "email")}),
        ("Horaires", {"fields": ("work_start_time", "work_end_time", "late_tolerance_minutes", "work_days")}),
    )
    list_filter = ("is_active", "city")
    search_fields = ("name", "ifu", "rccm")
    prepopulated_fields = {"slug": ("name",)}


from .models import Holiday  # noqa: E402


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name", "company")
    list_filter = ("company",)
