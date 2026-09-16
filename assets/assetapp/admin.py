from django.contrib import admin
from .models import Asset, AssetMaintenance, AssetDisposalRequest, AuditLog, WeeklyVehiclePlan, VehicleAssignment


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_no', 'category', 'purchase_value', 'net_book_value')
    search_fields = ('asset_no', 'description')
    list_filter = ('category',)


@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display = ('asset', 'maintenance_date', 'cost')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'model_name', 'user', 'timestamp')
    readonly_fields = [f.name for f in AuditLog._meta.fields]


@admin.register(AssetDisposalRequest)
class AssetDisposalRequestAdmin(admin.ModelAdmin):
    list_display = ("asset", "status", "declared_by", "declared_at", "reviewed_by")
    list_filter = ("status",)
    search_fields = ("asset__asset_no", "asset__description")


class VehicleAssignmentInline(admin.TabularInline):
    model = VehicleAssignment
    extra = 1


@admin.register(WeeklyVehiclePlan)
class WeeklyVehiclePlanAdmin(admin.ModelAdmin):
    list_display = ("week_start", "created_by", "created_at")
    inlines = [VehicleAssignmentInline]
