from django.contrib import admin

from .models import PayrollPeriod, PayrollSettings, Payslip, PayslipItem

admin.site.register(PayrollSettings)


@admin.register(PayrollPeriod)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ("company", "year", "month", "status")
    list_filter = ("company", "status")


class ItemInline(admin.TabularInline):
    model = PayslipItem
    extra = 0


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee", "period", "gross", "net")
    list_filter = ("company", "period")
    inlines = [ItemInline]
