from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from .models import (Profile, Department, ExitProcessStep, ExitProcess, Unit)


@admin.register(Profile)
class ProfileAdmin(UserAdmin):
    model = Profile
    list_display = ('username', 'email', 'first_name', 'last_name', 'program_area', 'profile_type',
                    'department', 'is_staff', 'status')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('program_area', 'profile_type', 'title', 'designation', 'phone', 'address', 'device_hash',
                           'department',  'unit', 'status', 'is_CMT', 'can_review', 'signature')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('program_area', 'profile_type', 'title', 'designation', 'phone', 'address', 'device_hash',
                           'department', 'unit', 'status', 'is_CMT', 'can_review', 'signature')}),)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'head')

    def get_queryset(self, request):
        return Department.objects.all()


class ExitProcessStepInline(admin.TabularInline):
    model = ExitProcessStep
    extra = 0
    fields = ("step_type", "status", "step_order", "updated_at", "updated_by")
    readonly_fields = ("step_type", "step_order", "updated_at", "updated_by")


@admin.register(ExitProcess)
class ExitProcessAdmin(admin.ModelAdmin):
    list_display = ("staff", "created_at")
    search_fields = ("staff__username", "staff__first_name", "staff__last_name", "staff__email")
    inlines = [ExitProcessStepInline]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('department', 'name', 'head')