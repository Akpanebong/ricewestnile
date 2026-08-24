from django.contrib import admin
from .models import Leave, Attendance, Training, \
    StaffDevice, LeaveDocument, Supervisor, SpecialLeaveType, LeaveType, SituationReport
from .employee_models import (BankDetail, Employee, Dependant, EducationHistory, EmergencyContact, EmployeeAddress,
EmployeeContact, EmployeePersonalInfo, WorkExperience,)
from .orientation_models import OrientationPlan, OrientationSession

# ---------------------------
# Leave Admin
# ---------------------------
@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("leave_type", "status")
    readonly_fields = ("applied_date", "supervisor_approved_at", "hr_approved_at", "ed_approved_at")


@admin.register(LeaveDocument)
class LeaveDocumentAdmin(admin.ModelAdmin):
    list_display = ("leave", "file", "created_at")


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = ["profile"]


# ---------------------------
# Attendance Admin
# ---------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'status')
    list_filter = ('status',)
    search_fields = ('employee__user__username', 'employee__user__first_name', 'employee__user__last_name')
    date_hierarchy = 'date'


# ---------------------------
# Training Admin
# ---------------------------
@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'end_date', 'participants_count')
    search_fields = ('title',)
    date_hierarchy = 'start_date'

    def participants_count(self, obj):
        return obj.participants.count()
    participants_count.short_description = 'Participants'


# ---------------------------
# Staffs Device
# ---------------------------
# Inline devices inside Employee profile
class StaffDeviceInline(admin.TabularInline):
    model = StaffDevice
    extra = 0
    readonly_fields = ("device_hash", "ip_address", "user_agent", "created_at", "approved")


class EmployeePersonalInfoInline(admin.StackedInline):
    model = EmployeePersonalInfo
    extra = 0
    max_num = 1


class EmployeeAddressInline(admin.TabularInline):
    model = EmployeeAddress
    extra = 1


class EmployeeContactInline(admin.TabularInline):
    model = EmployeeContact
    extra = 1


class EmergencyContactInline(admin.TabularInline):
    model = EmergencyContact
    extra = 1


class DependantInline(admin.TabularInline):
    model = Dependant
    extra = 1


class EducationHistoryInline(admin.TabularInline):
    model = EducationHistory
    extra = 1


class WorkExperienceInline(admin.TabularInline):
    model = WorkExperience
    extra = 1


class BankDetailInline(admin.StackedInline):
    model = BankDetail
    extra = 0
    max_num = 1


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("user", "staff_id", "job_title", "date_joined")
    search_fields = ("user__username","user__first_name", "user__last_name", "user__email", "staff_id", "job_title",)
    list_filter = ("user__first_name", "user__last_name", "date_joined")
    readonly_fields = ("slug",)
    actions = ["reset_device"]

    def device_status(self, obj):
        return "🔒 Bound" if obj.device_hash else "🔓 Not Bound"

    device_status.short_description = "Device Status"

    def reset_device(self, request, queryset):
        queryset.update(device_hash=None)
        self.message_user(request, f"✅ {queryset.count()} employees' devices reset.")

    reset_device.short_description = "Reset device binding"

    fieldsets = (
        ("Account & Work", {
            "fields": (
                "user",
                "staff_id",
                "job_title",
                "department",
                "supervised_by",
                "date_joined",
                # "employment_status",
                "slug",
            )
        }),
    )
    inlines = [
        EmployeePersonalInfoInline,
        EmployeeAddressInline,
        EmployeeContactInline,
        EmergencyContactInline,
        DependantInline,
        EducationHistoryInline,
        WorkExperienceInline,
        BankDetailInline,
    ]



@admin.register(OrientationPlan)
class OrientationPlanAdmin(admin.ModelAdmin):
    list_display = ("staff", "status", "completion_percent", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("staff__username", "staff__first_name", "staff__last_name", "staff__email")


@admin.register(OrientationSession)
class OrientationSessionAdmin(admin.ModelAdmin):
    list_display = ("staff", "unit", "status", "scheduled_start", "scheduled_end", "completed_at")
    list_filter = ("status", "unit")
    search_fields = ("plan__staff__username", "plan__staff__first_name", "plan__staff__last_name", "unit__name")



admin.site.register(SpecialLeaveType)
admin.site.register(LeaveType)
admin.site.register(SituationReport)
