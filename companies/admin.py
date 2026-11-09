from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "phone", "email", "is_active")
    list_filter = ("is_active", "city")
    search_fields = ("name", "ifu", "rccm")
    prepopulated_fields = {"slug": ("name",)}
