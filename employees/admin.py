from django.contrib import admin

from .models import Contract, Department, Employee, Position


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "head")
    list_filter = ("company",)
    search_fields = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "company", "base_salary")
    list_filter = ("company", "department")
    search_fields = ("title",)


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("matricule", "last_name", "first_name", "department", "position", "status", "company")
    list_filter = ("company", "status", "department")
    search_fields = ("matricule", "first_name", "last_name", "email", "cnss_number")
    inlines = [ContractInline]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("employee", "contract_type", "start_date", "end_date", "base_salary", "is_current")
    list_filter = ("contract_type", "is_current", "company")
