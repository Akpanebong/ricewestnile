from django.contrib import admin
from .models import (
    Supplier, ProcurementPlan, ProcurementPlanItem,
    Requisition, RequisitionItem, AuditLog, RFQ, Product, RFQSendLog,
    SupplierSpendReport, PurchaseOrder
)


class ProcurementPlanItemInline(admin.TabularInline):
    model = ProcurementPlanItem
    extra = 0


@admin.register(ProcurementPlan)
class ProcurementPlanAdmin(admin.ModelAdmin):
    list_display = ('number','requester','project','fiscal_year','budget_period','status','total_amount','created_at')
    search_fields = ('number','requester__username','requester__first_name','project__name','fiscal_year')
    list_filter = ('status','fiscal_year','budget_period')
    inlines = [ProcurementPlanItemInline]


class RequisitionItemInline(admin.TabularInline):
    model = RequisitionItem
    extra = 0


@admin.register(Requisition)
class POAdmin(admin.ModelAdmin):
    list_display = ('number','total','date')
    search_fields = ('number','supplier__name')
    inlines = [RequisitionItemInline]


@admin.register(RFQSendLog)
class RFQSendLogAdmin(admin.ModelAdmin):
    list_display = ('rfq', 'supplier', 'amount', 'date_sent')
    list_filter = ('date_sent', 'supplier')


@admin.register(SupplierSpendReport)
class SupplierSpendReportAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'total_spent', 'last_updated')


admin.site.register(Product)
admin.site.register(Supplier)
admin.site.register(AuditLog)
admin.site.register(RequisitionItem)
admin.site.register(RFQ)
admin.site.register(PurchaseOrder)
