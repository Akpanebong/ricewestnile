from django.contrib import admin
from .models import Asset, AssetMaintenance, AuditLog


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
